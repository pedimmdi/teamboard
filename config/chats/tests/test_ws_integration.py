from uuid import uuid4

from asgiref.sync import async_to_sync
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from datetime import datetime, timezone as dt_timezone
from django.utils import timezone

from accounts.models import UserSession
from rest_framework_simplejwt.tokens import RefreshToken
from channels.testing import WebsocketCommunicator
from config.asgi import application
from chats.services import (
    get_or_create_direct_chat,
    get_or_create_project_chat,
    create_chat_message,
    update_chat_message,
    delete_chat_message,
)
from projects.models import Project, ProjectMembership
from workspaces.models import Workspace, WorkspaceMembership
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer


User = get_user_model()


class ChatWebSocketIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="ws-owner@example.com",
            password="Strong-password-2026!",
        )
        self.member = User.objects.create_user(
            email="ws-member@example.com",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            email="ws-outsider@example.com",
            password="Strong-password-2026!",
        )

        self.workspace = Workspace.objects.create(
            name="WebSocket Integration Workspace",
        )

        for user, role in (
            (self.owner, WorkspaceMembership.Role.OWNER),
            (self.member, WorkspaceMembership.Role.MEMBER),
        ):
            WorkspaceMembership.objects.create(
                workspace=self.workspace,
                user=user,
                role=role,
            )

        self.direct = get_or_create_direct_chat(
            workspace_slug=self.workspace.slug,
            recipient=self.member,
            actor=self.owner,
        )

    def create_project_chat(self):
        with transaction.atomic():
            project = Project.objects.create(
                workspace=self.workspace,
                name="WebSocket Integration Project",
                created_by=self.owner,
            )

            ProjectMembership.objects.create(
                project=project,
                user=self.owner,
                role=ProjectMembership.Role.MANAGER,
            )

            ProjectMembership.objects.create(
                project=project,
                user=self.member,
                role=ProjectMembership.Role.MEMBER,
            )

        return get_or_create_project_chat(
            workspace_slug=self.workspace.slug,
            project_id=project.pk,
            actor=self.owner,
        )

    def token_for(self, user):
        refresh = RefreshToken.for_user(user)

        session = UserSession.objects.create(
            user=user,
            expires_at=datetime.fromtimestamp(
                refresh["exp"],
                tz=dt_timezone.utc,
            ),
            refresh_token_jti=str(refresh["jti"]),
        )

        refresh["session_id"] = str(session.id)

        return str(refresh.access_token)

    def websocket(self, conversation_id, *, token=None, origin=None):
        protocols = (
            ["jwt", token]
            if token is not None
            else []
        )

        communicator = WebsocketCommunicator(
            application,
            (
                f"/ws/chats/{self.workspace.slug}/"
                f"{conversation_id}/"
            ),
            subprotocols=protocols,
            headers=[
                (
                    b"origin",
                    (origin or settings.FRONTEND_URL).encode(),
                ),
            ],
        )
        return communicator

    async def assert_connection(self, communicator, *, expected):
        connected, subprotocol = await communicator.connect()

        self.assertEqual(connected, expected)

        if connected:
            # The JWT must never be echoed as the
            # negotiated WebSocket subprotocol.
            self.assertEqual(subprotocol, "jwt")
            await communicator.disconnect()

    def test_valid_jwt_connects_to_own_direct_chat(self):
        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=self.token_for(self.owner),
            ),
            expected=True,
        )

    def test_valid_jwt_connects_to_project_chat(self):
        project_chat = self.create_project_chat()

        async_to_sync(self.assert_connection)(
            self.websocket(
                project_chat.pk,
                token=self.token_for(self.member),
            ),
            expected=True,
        )

    def test_missing_jwt_is_rejected(self):
        async_to_sync(self.assert_connection)(
            self.websocket(self.direct.pk),
            expected=False,
        )

    def test_invalid_jwt_is_rejected(self):
        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token="invalid-token",
            ),
            expected=False,
        )

    def test_outsider_cannot_access_direct_chat(self):
        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=self.token_for(self.outsider),
            ),
            expected=False,
        )

    def test_outsider_cannot_access_project_chat(self):
        project_chat = self.create_project_chat()

        async_to_sync(self.assert_connection)(
            self.websocket(
                project_chat.pk,
                token=self.token_for(self.outsider),
            ),
            expected=False,
        )

    def test_unknown_conversation_is_rejected(self):
        async_to_sync(self.assert_connection)(
            self.websocket(
                uuid4(),
                token=self.token_for(self.owner),
            ),
            expected=False,
        )

    def test_untrusted_origin_is_rejected(self):
        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=self.token_for(self.owner),
                origin="https://untrusted.example",
            ),
            expected=False,
        )

    def test_removed_workspace_member_cannot_reconnect(self):
        WorkspaceMembership.objects.filter(
            workspace=self.workspace,
            user=self.member,
        ).delete()

        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=self.token_for(self.member),
            ),
            expected=False,
        )

    def test_jwt_without_session_is_rejected(self):
        token = str(RefreshToken.for_user(self.owner).access_token)

        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=token,
            ),
            expected=False,
        )

    def test_revoked_session_is_rejected(self):
        token = self.token_for(self.owner)

        UserSession.objects.filter(
            user=self.owner,
        ).update(
            revoked_at=timezone.now(),
        )

        async_to_sync(self.assert_connection)(
            self.websocket(
                self.direct.pk,
                token=token,
            ),
            expected=False,
        )

    async def send_test_event(
        self, conversation_id, event_type, message_id
    ):
        layer = get_channel_layer()

        await layer.group_send(
            f"chat.{conversation_id.hex}",
            {
                "type": "chat.event",
                "event_type": event_type,
                "message_id": str(message_id),
            },
        )

    async def assert_message_events(self, token):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        try:
            message_id = await database_sync_to_async(
                lambda: create_chat_message(
                    workspace_slug=self.workspace.slug,
                    conversation_id=self.direct.pk,
                    actor=self.owner,
                    content="Hello realtime",
                ).pk
            )()

            created = await communicator.receive_json_from(
                timeout=5
            )

            self.assertEqual(
                created["type"], "message.created"
            )
            self.assertEqual(
                created["message"]["id"], str(message_id)
            )
            self.assertEqual(
                created["message"]["content"],
                "Hello realtime",
            )

            await database_sync_to_async(
                update_chat_message
            )(
                workspace_slug=self.workspace.slug,
                message_id=message_id,
                actor=self.owner,
                content="Edited realtime",
            )

            updated = await communicator.receive_json_from(
                timeout=5
            )

            self.assertEqual(
                updated["type"], "message.updated"
            )
            self.assertEqual(
                updated["message"]["content"],
                "Edited realtime",
            )
            self.assertIsNotNone(
                updated["message"]["edited_at"]
            )

            await database_sync_to_async(
                delete_chat_message
            )(
                workspace_slug=self.workspace.slug,
                message_id=message_id,
                actor=self.owner,
            )

            deleted = await communicator.receive_json_from(
                timeout=5
            )

            self.assertEqual(
                deleted["type"], "message.deleted"
            )
            self.assertEqual(
                deleted["message"]["id"], str(message_id)
            )
            self.assertEqual(
                deleted["message"]["content"], ""
            )
            self.assertEqual(
                deleted["message"]["attachments"], []
            )
            self.assertIsNotNone(
                deleted["message"]["deleted_at"]
            )
        finally:
            await communicator.disconnect()

    def test_realtime_create_update_delete(self):
        token = self.token_for(self.member)

        async_to_sync(
            self.assert_message_events
        )(token)

    async def assert_revoked_session_closes_on_event(
        self, token, message_id
    ):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await database_sync_to_async(
            lambda: UserSession.objects.filter(
                user=self.member
            ).update(revoked_at=timezone.now())
        )()

        await self.send_test_event(
            self.direct.pk,
            "message.created",
            message_id,
        )

        response = await communicator.receive_output(
            timeout=5
        )

        self.assertEqual(
            response["type"], "websocket.close"
        )
        self.assertEqual(response["code"], 4401)

    def test_revoked_session_closes_existing_connection(self):
        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.direct.pk,
            actor=self.owner,
            content="Private message",
        )

        token = self.token_for(self.member)

        async_to_sync(
            self.assert_revoked_session_closes_on_event
        )(token, message.pk)

    async def assert_removed_member_closes_on_event(
        self, token, message_id
    ):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await database_sync_to_async(
            lambda: WorkspaceMembership.objects.filter(
                workspace=self.workspace,
                user=self.member,
            ).delete()
        )()

        await self.send_test_event(
            self.direct.pk,
            "message.created",
            message_id,
        )

        response = await communicator.receive_output(
            timeout=5
        )

        self.assertEqual(
            response["type"], "websocket.close"
        )
        self.assertEqual(response["code"], 4403)

    def test_removed_member_closes_existing_connection(self):
        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=self.direct.pk,
            actor=self.owner,
            content="Private message",
        )

        token = self.token_for(self.member)

        async_to_sync(
            self.assert_removed_member_closes_on_event
        )(token, message.pk)

    async def assert_no_cross_conversation_event(
        self, token, other_conversation_id, message_id
    ):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        try:
            await self.send_test_event(
                other_conversation_id,
                "message.created",
                message_id,
            )

            self.assertTrue(
                await communicator.receive_nothing(
                    timeout=0.3
                )
            )
        finally:
            await communicator.disconnect()

    def test_other_conversation_events_are_isolated(self):
        other_conversation = self.create_project_chat()

        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=other_conversation.pk,
            actor=self.owner,
            content="Project-only message",
        )

        async_to_sync(
            self.assert_no_cross_conversation_event
        )(
            self.token_for(self.member),
            other_conversation.pk,
            message.pk,
        )

    async def assert_project_chat_event(
        self, conversation_id, token
    ):
        communicator = self.websocket(
            conversation_id,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        try:
            message_id = await database_sync_to_async(
                lambda: create_chat_message(
                    workspace_slug=self.workspace.slug,
                    conversation_id=conversation_id,
                    actor=self.owner,
                    content="Project realtime message",
                ).pk
            )()

            event = await communicator.receive_json_from(
                timeout=5
            )

            self.assertEqual(
                event["type"], "message.created"
            )
            self.assertEqual(
                event["message"]["id"], str(message_id)
            )
            self.assertEqual(
                event["message"]["content"],
                "Project realtime message",
            )
        finally:
            await communicator.disconnect()

    def test_project_chat_receives_realtime_message(self):
        project_chat = self.create_project_chat()
        token = self.token_for(self.member)

        async_to_sync(self.assert_project_chat_event)(
            project_chat.pk,
            token,
        )

    async def assert_removed_project_member(
        self, conversation_id, project_id, token, message_id
    ):
        communicator = self.websocket(
            conversation_id,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await database_sync_to_async(
            lambda: ProjectMembership.objects.filter(
                project_id=project_id,
                user=self.member,
            ).delete()
        )()

        await self.send_test_event(
            conversation_id,
            "message.created",
            message_id,
        )

        response = await communicator.receive_output(
            timeout=5
        )

        self.assertEqual(
            response["type"], "websocket.close"
        )
        self.assertEqual(response["code"], 4403)

    def test_removed_project_member_closes_existing_connection(self):
        project_chat = self.create_project_chat()

        message = create_chat_message(
            workspace_slug=self.workspace.slug,
            conversation_id=project_chat.pk,
            actor=self.owner,
            content="Project private message",
        )

        token = self.token_for(self.member)

        async_to_sync(self.assert_removed_project_member)(
            project_chat.pk,
            project_chat.project_id,
            token,
            message.pk,
        )

    async def assert_rollback_sends_no_event(
        self, token
    ):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        def create_then_rollback():
            try:
                with transaction.atomic():
                    create_chat_message(
                        workspace_slug=self.workspace.slug,
                        conversation_id=self.direct.pk,
                        actor=self.owner,
                        content="Rolled back message",
                    )
                    raise RuntimeError("Force rollback")
            except RuntimeError:
                pass

        try:
            await database_sync_to_async(
                create_then_rollback
            )()

            self.assertTrue(
                await communicator.receive_nothing(
                    timeout=0.5
                )
            )
        finally:
            await communicator.disconnect()

    def test_rollback_does_not_publish_websocket_event(self):
        token = self.token_for(self.member)

        async_to_sync(
            self.assert_rollback_sends_no_event
        )(token)

    async def assert_client_cannot_send_message(
        self, token
    ):
        communicator = self.websocket(
            self.direct.pk,
            token=token,
        )

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.send_json_to({
            "type": "message.created",
            "content": "Unauthorized websocket mutation",
        })

        response = await communicator.receive_output(
            timeout=5
        )

        self.assertEqual(
            response["type"], "websocket.close"
        )
        self.assertEqual(response["code"], 4400)

    def test_client_websocket_mutation_is_rejected(self):
        token = self.token_for(self.member)

        async_to_sync(
            self.assert_client_cannot_send_message
        )(token)

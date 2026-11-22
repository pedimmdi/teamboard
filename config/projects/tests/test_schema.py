from pathlib import Path

import yaml
from django.conf import settings
from django.test import SimpleTestCase
from drf_spectacular.generators import SchemaGenerator


class ProjectSchemaTests(SimpleTestCase):
    def test_schema_includes_projects_without_duplicate_pagination(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        self.assertIn("/api/v1/workspaces/{slug}/projects/", schema["paths"])
        self.assertFalse(any(name.startswith("PaginatedPaginated") for name in schema["components"]["schemas"]))
        response = schema["paths"]["/api/v1/workspaces/{slug}/projects/"]["get"]["responses"]["200"]
        self.assertEqual(response["content"]["application/json"]["schema"]["$ref"], "#/components/schemas/PaginatedProject")
        saved = yaml.safe_load((Path(settings.BASE_DIR) / "schema.yml").read_text())
        self.assertEqual(saved, schema)

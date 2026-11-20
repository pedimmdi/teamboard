from django.db import migrations

SQL = """
CREATE FUNCTION tasks_reminders_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.due_date IS DISTINCT FROM OLD.due_date THEN
        UPDATE tasks_taskreminder SET needs_recalculation = true
        WHERE task_id = NEW.id AND kind = 'relative' AND status IN ('pending','disabled','invalid','failed');
    END IF;
    IF NEW.status = 'done' AND OLD.status <> 'done' THEN
        UPDATE tasks_taskreminder SET status = 'cancelled', last_error = 'TaskCompleted', needs_recalculation = false
        WHERE task_id = NEW.id AND status IN ('pending','disabled','invalid','failed');
    END IF;
    RETURN NEW;
END; $$;
CREATE TRIGGER task_reminder_due_changes AFTER UPDATE OF due_date, status ON tasks_task
FOR EACH ROW EXECUTE FUNCTION tasks_reminders_changed();
"""
class Migration(migrations.Migration):
    dependencies = [("tasks", "0008_taskreminder")]
    operations = [migrations.RunSQL(SQL, "DROP TRIGGER task_reminder_due_changes ON tasks_task; DROP FUNCTION tasks_reminders_changed();")]

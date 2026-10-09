from django.db import migrations

# Events store the user type in their metadata. Roles are shifted by one level:
# a former "instructor" is a "coordinator", a former "guest" is an "instructor".
# Both statements must run in this order, so that events already renamed are not
# renamed twice.
FORWARD_SQL = [
    """
    UPDATE analytics_event
    SET metadata = jsonb_set(metadata, '{user_type}', '"coordinator"')
    WHERE metadata->>'user_type' = 'instructor';
    """,
    """
    UPDATE analytics_event
    SET metadata = jsonb_set(metadata, '{user_type}', '"instructor"')
    WHERE metadata->>'user_type' = 'guest';
    """,
]

REVERSE_SQL = [
    """
    UPDATE analytics_event
    SET metadata = jsonb_set(metadata, '{user_type}', '"guest"')
    WHERE metadata->>'user_type' = 'instructor';
    """,
    """
    UPDATE analytics_event
    SET metadata = jsonb_set(metadata, '{user_type}', '"instructor"')
    WHERE metadata->>'user_type' = 'coordinator';
    """,
]


class Migration(migrations.Migration):

    dependencies = [
        ("analytics", "0009_event_unique_id"),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, REVERSE_SQL),
    ]

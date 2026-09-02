import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0009_remove_assignmenttarget_assignment_target_exactly_one_reference_and_more"),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.AddConstraint(
            model_name="teammembership",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                name="team_membership_no_period_overlap",
                expressions=[
                    ("team", "="),
                    ("employee", "="),
                    (
                        models.Func(
                            models.F("valid_from"),
                            models.F("valid_to"),
                            models.Value("[)"),
                            function="TSTZRANGE",
                            output_field=django.contrib.postgres.fields.ranges.DateTimeRangeField(),
                        ),
                        "&&",
                    ),
                ],
            ),
        ),
    ]

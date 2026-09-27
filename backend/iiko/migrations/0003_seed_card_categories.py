from django.db import migrations


# User-provided directory, matched exactly to live iiko names on 2026-09-10.
ROWS = [('department', 'Грелка', '333ec2bc-f444-4bf6-af0b-4602e6c6acf3', 0),
 ('department', 'О!Пушка', '75973194-d4e7-4945-b7fc-2de831ed602c', 1),
 ('department', 'Ресторан Елена', '6793c9fa-8d2d-4e93-aae9-f3532f78260f', 2),
 ('department', 'Катадзе', '8a8b4454-bee2-4f5c-93e8-a7070d0f0dd0', 3),
 ('department', 'Wow Kitchen', 'd9468122-180c-4fce-884c-c8496a903211', 4),
 ('department', 'Wow Aparts', '3a940f30-efba-4baa-9a3a-9e3eb56a4b5f', 5),
 ('department', 'AYS Hotel', '380a85f3-856b-49ae-a0a4-9e3b60677c30', 6),
 ('department', 'Bunker', '820529c1-58cc-4c11-a1a1-751017c71afe', 7),
 ('department', 'Напойка', '3d76a86f-0212-4fc5-a880-73892985664c', 8),
 ('department', 'Каритшал', '827149ef-f488-429d-a9e9-f3c0a4cdea2f', 9),
 ('department', 'Профилак', 'cd3c5797-3430-4ddd-8790-a022c5676c4d', 10),
 ('department', 'Стройка', '98a35394-304e-487e-b261-a5b529c79415', 11),
 ('department', 'IT', '43d6f832-f4e0-4659-877f-5724c5727d60', 12),
 ('legalEntity', 'ООО Грелка', '0d4890af-c0f4-4568-a1a2-f55805b153ec', 0),
 ('legalEntity', 'ООО Аэроотель', 'f35f4f62-e37f-4b5f-a9bf-73eac924d12b', 1),
 ('legalEntity', 'ООО К1', 'f389a262-47cd-43cd-9ca3-3859a3a80042', 2),
 ('legalEntity', 'ООО Трансавангард', '331e45a7-caa3-46b7-aecd-2859d841e57d', 3),
 ('legalEntity', 'ООО Барс', '53a8b0c7-7918-4f2a-9b17-c943613bb343', 4),
 ('legalEntity', 'ООО Северный Мустаг', 'acb25810-8617-47a2-b217-0909a7a9e1bd', 5),
 ('cardType', 'Карта питания', '12db95b7-3f4d-4ba7-9776-0577ad788986', 0),
 ('cardType', 'Депозитная карта', 'b564e5d4-99ec-44bf-b458-971fd62dfe8b', 1),
 ('cardType', 'Карта партнера', 'a01308ac-ff28-4d4d-bb4c-d226f63a3569', 2),
 ('approval', 'Без согласования', 'df9c9d05-e1e5-412e-9666-03f371e49d76', 0)]


def seed(apps, schema_editor):
    model = apps.get_model("iiko", "CardCategory")
    for field, name, external_id, position in ROWS:
        model.objects.using(schema_editor.connection.alias).get_or_create(
            connection_id="sheregesh", organization_id="07727ae8-4b93-4529-ac85-9232fae45be3",
            external_id=external_id, defaults={"field": field, "name": name, "position": position},
        )


class Migration(migrations.Migration):
    dependencies = [("iiko", "0002_cardcategory")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

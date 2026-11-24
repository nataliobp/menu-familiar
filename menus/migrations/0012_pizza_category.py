from django.db import migrations


def add_pizza(apps, schema_editor):
    categories = apps.get_model("menus", "CategoryRecord").objects.using(schema_editor.connection.alias)
    categories.create(key="pizza", name_ca="Pizza")


def remove_pizza(apps, schema_editor):
    categories = apps.get_model("menus", "CategoryRecord").objects.using(schema_editor.connection.alias)
    categories.filter(key="pizza").delete()


class Migration(migrations.Migration):
    dependencies = [("menus", "0011_catalogue_source")]
    operations = [migrations.RunPython(add_pizza, remove_pizza)]

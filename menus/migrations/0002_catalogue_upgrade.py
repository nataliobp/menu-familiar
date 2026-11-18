from django.db import migrations, models
import django.db.models.deletion


CATEGORIES = (
    ("legumes", "Llegums"), ("vegetables", "Verdures"), ("cereals", "Cereals"),
    ("salads", "Amanides"), ("creams", "Cremes"), ("soups", "Sopes"),
    ("chicken", "Pollastre"), ("beef", "Vedella"), ("pork", "Porc"),
    ("pasta", "Pasta"), ("eggs", "Ous"), ("fish", "Peix"), ("fried", "Fregits"),
)


def upgrade(apps, schema_editor):
    Category = apps.get_model("menus", "CategoryRecord")
    Dish = apps.get_model("menus", "DishRecord")
    Secondary = apps.get_model("menus", "SecondaryCategoryRecord")
    mapping = {name: key for key, name in CATEGORIES}
    Category.objects.bulk_create([Category(key=key, name_ca=name) for key, name in CATEGORIES])
    for dish in Dish.objects.all().iterator():
        if (dish.primary_category not in mapping or not dish.name.strip() or len(dish.name) > 200
                or dish.id < 1 or dish.id >= 9223372036854775807
                or dish.meal_preference not in ("lunch", "dinner", "both")):
            raise ValueError("Invalid legacy catalogue data")
        dish.category_ref_id = mapping[dish.primary_category]
        dish.save(update_fields=["category_ref"])
    for secondary in Secondary.objects.select_related("dish").iterator():
        if secondary.name not in mapping or secondary.name == secondary.dish.primary_category:
            raise ValueError("Invalid legacy catalogue category")
        secondary.category_id = mapping[secondary.name]
        secondary.save(update_fields=["category"])


def downgrade(apps, schema_editor):
    Dish = apps.get_model("menus", "DishRecord")
    Secondary = apps.get_model("menus", "SecondaryCategoryRecord")
    for dish in Dish.objects.select_related("category_ref").iterator():
        dish.primary_category = dish.category_ref.name_ca
        dish.save(update_fields=["primary_category"])
    for secondary in Secondary.objects.select_related("category").iterator():
        secondary.name = secondary.category.name_ca
        secondary.save(update_fields=["name"])


class Migration(migrations.Migration):
    dependencies = [("menus", "0001_initial")]
    operations = [
        migrations.CreateModel(name="CategoryRecord", fields=[("key", models.CharField(max_length=32, primary_key=True, serialize=False)), ("name_ca", models.CharField(max_length=60, unique=True))]),
        migrations.AddField(model_name="dishrecord", name="category_ref", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="menus.categoryrecord")),
        migrations.AddField(model_name="secondarycategoryrecord", name="category", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to="menus.categoryrecord")),
        migrations.AddField(model_name="dishrecord", name="archived", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="dishrecord", name="version", field=models.PositiveBigIntegerField(default=1)),
        migrations.RunPython(upgrade, downgrade),
        migrations.RemoveConstraint(model_name="secondarycategoryrecord", name="unique_dish_secondary_category"),
        migrations.RemoveField(model_name="secondarycategoryrecord", name="name"),
        migrations.RemoveField(model_name="dishrecord", name="primary_category"),
        migrations.RenameField(model_name="dishrecord", old_name="category_ref", new_name="primary_category"),
        migrations.AlterField(model_name="dishrecord", name="primary_category", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menus.categoryrecord")),
        migrations.AlterField(model_name="secondarycategoryrecord", name="category", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="menus.categoryrecord")),
        migrations.AlterField(model_name="dishrecord", name="id", field=models.BigAutoField(primary_key=True, serialize=False)),
        migrations.AlterField(model_name="dishrecord", name="name", field=models.CharField(max_length=200)),
        migrations.AddConstraint(model_name="secondarycategoryrecord", constraint=models.UniqueConstraint(fields=("dish", "category"), name="unique_dish_secondary_category")),
        migrations.AddConstraint(model_name="dishrecord", constraint=models.CheckConstraint(condition=models.Q(id__gte=1), name="dish_id_positive")),
        migrations.AddConstraint(model_name="dishrecord", constraint=models.CheckConstraint(condition=models.Q(version__gte=1), name="dish_version_positive")),
        migrations.AddConstraint(model_name="dishrecord", constraint=models.CheckConstraint(condition=models.Q(meal_preference__in=["lunch", "dinner", "both"]), name="dish_preference_valid")),
    ]

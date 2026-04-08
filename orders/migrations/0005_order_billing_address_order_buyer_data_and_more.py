# Generated manually for iyzico checkout and delivery support.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_orderitem_beat_license"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="billing_address",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="buyer_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_token",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_token_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="order",
            name="shipping_address",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="order",
            name="payment_provider",
            field=models.CharField(default="iyzico", max_length=50),
        ),
    ]

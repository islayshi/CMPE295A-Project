from django.db import migrations, models

CHOICES = [
    ("unet", "U-Net (Spatial Segmentation)"),
    ("pinn", "PINN (Physics-Informed Neural Network)"),
    ("rl", "RL Agent (DQN/PPO Progression)"),
    ("ensemble", "Ensemble (Combined Voting)"),
    ("fusion", "Fusion UNet (Physics-Informed)"),
    ("mock", "Mock (MOCK_INFERENCE=True fixture)"),
]


class Migration(migrations.Migration):
    """Adds "fusion" (the physics-informed fusion UNet service) to the source_model / model_name choices.
    Choices are not enforced by the database, so this changes no table."""

    dependencies = [
        ("predictions", "0004_remove_predictionpolygon_risk_label"),
    ]

    operations = [
        migrations.AlterField(
            model_name="predictionpolygon",
            name="source_model",
            field=models.CharField(choices=CHOICES, help_text="Which ML model produced this prediction.", max_length=50),
        ),
        migrations.AlterField(
            model_name="modelperformancemetric",
            name="model_name",
            field=models.CharField(choices=CHOICES, help_text="Which model these metrics are for.", max_length=50),
        ),
    ]

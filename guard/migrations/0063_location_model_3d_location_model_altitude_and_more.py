from django.db import migrations, models

import guard.models


class Migration(migrations.Migration):

    dependencies = [
        ('guard', '0062_ad_enddate_ad_startdate'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='model_3d',
            field=models.FileField(blank=True, help_text='Optional glTF binary (.glb) of this landmark. Keep it small — it is downloaded for offline use and rendered on the map. Model origin should sit at the building\'s ground centre, +Z up, facing north.', null=True, upload_to=guard.models.location_model_path, verbose_name='3D Model'),
        ),
        migrations.AddField(
            model_name='location',
            name='model_scale',
            field=models.FloatField(default=1.0, help_text='Uniform scale multiplier. 1.0 means the model is already in metres.', verbose_name='Model Scale'),
        ),
        migrations.AddField(
            model_name='location',
            name='model_rotation',
            field=models.FloatField(default=0.0, help_text='Heading in degrees clockwise from north, to align the model with the real building.', verbose_name='Model Rotation'),
        ),
        migrations.AddField(
            model_name='location',
            name='model_altitude',
            field=models.FloatField(default=0.0, help_text='Vertical offset in metres, to lift or sink the model relative to the ground.', verbose_name='Model Altitude'),
        ),
    ]

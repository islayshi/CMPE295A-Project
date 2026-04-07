import pyretechnics.fuel_models as fm
import pyretechnics.surface_fire as sf

fuel_model = fm.get_fuel_model(101)

fuel_moisture = (
    0.05,
    0.10,
    0.15,
    0.00,
    0.90,
    0.60,
)

moisturized_fuel_model = fm.moisturize(fuel_model, fuel_moisture)

surface_fire_min = sf.calc_surface_fire_behavior_no_wind_no_slope(
    moisturized_fuel_model
)

surface_fire_max = sf.calc_surface_fire_behavior_max(
    surface_fire_min,
    midflame_wind_speed=500.0,
    upwind_direction=215.0,
    slope=0.2,
    aspect=270.0,
    surface_lw_ratio_model="rothermel"
)

print(surface_fire_max)
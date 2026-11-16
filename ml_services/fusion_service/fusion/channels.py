"""The 33 input layers of the fusion UNet, in training order (WildfirePINN rl/ens/fusion_data.py, frozen 9 Nov 2026)."""
CH = ["unet_seed1", "unet_seed3", "unet_seed6", "unet_goes1", "unet_goes3", "unet_goes6",
      "pinn1", "pinn3", "pinn6", "pinn_goes1", "pinn_goes3", "pinn_goes6",
      "burnable", "ros_raw", "ros_cal", "pinn_start",
      "viirs_prior", "viirs_recent", "goes_burned24",
      "goes_fire_now", "goes_fire_3h", "goes_fire_24h", "tmp_c", "rh", "wind_u", "wind_v", "gust", "precip",
      "elevation", "slope", "ndvi", "has_unet", "has_goes_fire"]
IDX = {c: i for i, c in enumerate(CH)}
CROP = 32

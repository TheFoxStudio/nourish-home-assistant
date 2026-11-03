"""Constants for Nourish."""

DOMAIN = "nourish"
DEFAULT_URL = "https://food.orktork.space"
DEFAULT_INTERVAL = 15
CONF_INTERVAL = "poll_interval"
METRICS = {
    "calories": ("Calories", "kcal", "mdi:fire", "energy"),
    "protein": ("Protein", "g", "mdi:food-steak", "mass"),
    "carbs": ("Carbohydrates", "g", "mdi:bread-slice", "mass"),
    "fat": ("Fat", "g", "mdi:oil", "mass"),
    "fiber": ("Fiber", "g", "mdi:barley", "mass"),
    "sugar": ("Sugar", "g", "mdi:spoon-sugar", "mass"),
    "waterMl": ("Water", "mL", "mdi:water", "volume"),
}

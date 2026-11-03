"""Today's nutrient sensors and links to imported daily statistics."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import DOMAIN, METRICS


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(NourishSensor(entry.runtime_data, key) for key in METRICS)


class NourishSensor(CoordinatorEntity, SensorEntity):
    """A current-day measurement, allowed to decrease after corrections."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        name, unit, icon, _ = METRICS[key]
        self._attr_name = f"{name} today"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="Nourish",
            model="Food and water tracking",
        )

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=0)
        )

    @callback
    def _midnight(self, now):
        self.async_write_ha_state()

    @property
    def native_value(self):
        totals = self.coordinator.daily_totals
        return totals.get(dt_util.now().date().isoformat(), {}).get(self.key, 0.0)

    @property
    def extra_state_attributes(self):
        return {
            "date": dt_util.now().date().isoformat(),
            "daily_statistic_id": f"{DOMAIN}:{self.coordinator.entry.entry_id}_{self.key.lower()}",
            "last_sync": self.coordinator.data.get("generated_at"),
        }

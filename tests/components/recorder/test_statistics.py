"""The tests for sensor recorder platform."""
# pylint: disable=invalid-name
from datetime import datetime, timedelta
import importlib
import sys
from unittest.mock import ANY, DEFAULT, MagicMock, patch, sentinel

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import history, statistics
from homeassistant.components.recorder.const import SQLITE_URL_PREFIX
from homeassistant.components.recorder.db_schema import StatisticsShortTerm
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.components.recorder.statistics import (
    STATISTIC_UNIT_TO_UNIT_CONVERTER,
    _statistics_during_period_with_session,
    _update_or_add_metadata,
    async_add_external_statistics,
    async_import_statistics,
    delete_statistics_duplicates,
    delete_statistics_meta_duplicates,
    get_last_short_term_statistics,
    get_last_statistics,
    get_latest_short_term_statistics,
    get_metadata,
    list_statistic_ids,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.components.sensor import UNIT_CONVERTERS
from homeassistant.const import UnitOfTemperature
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from .common import (
    assert_dict_of_states_equal_without_context_and_last_changed,
    async_wait_recording_done,
    do_adhoc_statistics,
    statistics_during_period,
    wait_recording_done,
)

from tests.common import get_test_home_assistant, mock_registry

ORIG_TZ = dt_util.DEFAULT_TIME_ZONE


def test_converters_align_with_sensor():
    """Ensure STATISTIC_UNIT_TO_UNIT_CONVERTER is aligned with UNIT_CONVERTERS."""
    for converter in UNIT_CONVERTERS.values():
        assert converter in STATISTIC_UNIT_TO_UNIT_CONVERTER.values()

    for converter in STATISTIC_UNIT_TO_UNIT_CONVERTER.values():
        assert converter in UNIT_CONVERTERS.values()


def test_compile_hourly_statistics(hass_recorder):
    """Test compiling hourly statistics."""
    hass = hass_recorder()
    instance = recorder.get_instance(hass)
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    # Should not fail if there is nothing there yet
    stats = get_latest_short_term_statistics(
        hass, ["sensor.test1"], {"last_reset", "max", "mean", "min", "state", "sum"}
    )
    assert stats == {}

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    do_adhoc_statistics(hass, start=four)
    wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero),
        "end": process_timestamp(zero + timedelta(minutes=5)),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_2 = {
        "start": process_timestamp(four),
        "end": process_timestamp(four + timedelta(minutes=5)),
        "mean": pytest.approx(20.0),
        "min": pytest.approx(20.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1, expected_2]
    expected_stats2 = [expected_1, expected_2]

    # Test statistics_during_period
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    # Test statistics_during_period with a far future start and end date
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(hass, future, end_time=future, period="5minute")
    assert stats == {}

    # Test statistics_during_period with a far future end date
    stats = statistics_during_period(hass, zero, end_time=future, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    stats = statistics_during_period(
        hass, zero, statistic_ids=["sensor.test2"], period="5minute"
    )
    assert stats == {"sensor.test2": expected_stats2}

    stats = statistics_during_period(
        hass, zero, statistic_ids=["sensor.test3"], period="5minute"
    )
    assert stats == {}

    # Test get_last_short_term_statistics and get_latest_short_term_statistics
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    stats = get_last_short_term_statistics(
        hass,
        1,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {"sensor.test1": [expected_2]}

    stats = get_latest_short_term_statistics(
        hass, ["sensor.test1"], {"last_reset", "max", "mean", "min", "state", "sum"}
    )
    assert stats == {"sensor.test1": [expected_2]}

    metadata = get_metadata(hass, statistic_ids=['sensor.test1"'])

    stats = get_latest_short_term_statistics(
        hass,
        ["sensor.test1"],
        {"last_reset", "max", "mean", "min", "state", "sum"},
        metadata=metadata,
    )
    assert stats == {"sensor.test1": [expected_2]}

    stats = get_last_short_term_statistics(
        hass,
        2,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {"sensor.test1": expected_stats1[::-1]}

    stats = get_last_short_term_statistics(
        hass,
        3,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {"sensor.test1": expected_stats1[::-1]}

    stats = get_last_short_term_statistics(
        hass,
        1,
        "sensor.test3",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    instance.get_session().query(StatisticsShortTerm).delete()
    # Should not fail there is nothing in the table
    stats = get_latest_short_term_statistics(
        hass, ["sensor.test1"], {"last_reset", "max", "mean", "min", "state", "sum"}
    )
    assert stats == {}


@pytest.fixture
def mock_sensor_statistics():
    """Generate some fake statistics."""

    def sensor_stats(entity_id, start):
        """Generate fake statistics."""
        return {
            "meta": {
                "has_mean": True,
                "has_sum": False,
                "name": None,
                "statistic_id": entity_id,
                "unit_of_measurement": "dogs",
            },
            "stat": {"start": start},
        }

    def get_fake_stats(_hass, start, _end):
        return statistics.PlatformCompiledStatistics(
            [
                sensor_stats("sensor.test1", start),
                sensor_stats("sensor.test2", start),
                sensor_stats("sensor.test3", start),
            ],
            get_metadata(
                _hass, statistic_ids=["sensor.test1", "sensor.test2", "sensor.test3"]
            ),
        )

    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        side_effect=get_fake_stats,
    ):
        yield


@pytest.fixture
def mock_from_stats():
    """Mock out Statistics.from_stats."""
    counter = 0
    real_from_stats = StatisticsShortTerm.from_stats

    def from_stats(metadata_id, stats):
        nonlocal counter
        if counter == 0 and metadata_id == 2:
            counter += 1
            return None
        return real_from_stats(metadata_id, stats)

    with patch(
        "homeassistant.components.recorder.statistics.StatisticsShortTerm.from_stats",
        side_effect=from_stats,
        autospec=True,
    ):
        yield


def test_compile_periodic_statistics_exception(
    hass_recorder, mock_sensor_statistics, mock_from_stats
):
    """Test exception handling when compiling periodic statistics."""

    hass = hass_recorder()
    setup_component(hass, "sensor", {})

    now = dt_util.utcnow()
    do_adhoc_statistics(hass, start=now)
    do_adhoc_statistics(hass, start=now + timedelta(minutes=5))
    wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(now),
        "end": process_timestamp(now + timedelta(minutes=5)),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_2 = {
        "start": process_timestamp(now + timedelta(minutes=5)),
        "end": process_timestamp(now + timedelta(minutes=10)),
        "mean": None,
        "min": None,
        "max": None,
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1, expected_2]
    expected_stats2 = [expected_2]
    expected_stats3 = [expected_1, expected_2]

    stats = statistics_during_period(hass, now, period="5minute")
    assert stats == {
        "sensor.test1": expected_stats1,
        "sensor.test2": expected_stats2,
        "sensor.test3": expected_stats3,
    }


def test_rename_entity(hass_recorder):
    """Test statistics is migrated when entity_id is changed."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})

    entity_reg = mock_registry(hass)

    @callback
    def add_entry():
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            "test",
            "unique_0000",
            suggested_object_id="test1",
        )
        assert reg_entry.entity_id == "sensor.test1"

    hass.add_job(add_entry)
    hass.block_till_done()

    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero),
        "end": process_timestamp(zero + timedelta(minutes=5)),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1]
    expected_stats2 = [expected_1]
    expected_stats99 = [expected_1]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    @callback
    def rename_entry():
        entity_reg.async_update_entity("sensor.test1", new_entity_id="sensor.test99")

    hass.add_job(rename_entry)
    wait_recording_done(hass)

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test99": expected_stats99, "sensor.test2": expected_stats2}


def test_rename_entity_collision(hass_recorder, caplog):
    """Test statistics is migrated when entity_id is changed."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})

    entity_reg = mock_registry(hass)

    @callback
    def add_entry():
        reg_entry = entity_reg.async_get_or_create(
            "sensor",
            "test",
            "unique_0000",
            suggested_object_id="test1",
        )
        assert reg_entry.entity_id == "sensor.test1"

    hass.add_job(add_entry)
    hass.block_till_done()

    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    for kwargs in ({}, {"statistic_ids": ["sensor.test1"]}):
        stats = statistics_during_period(hass, zero, period="5minute", **kwargs)
        assert stats == {}
    stats = get_last_short_term_statistics(
        hass,
        0,
        "sensor.test1",
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert stats == {}

    do_adhoc_statistics(hass, start=zero)
    wait_recording_done(hass)
    expected_1 = {
        "start": process_timestamp(zero),
        "end": process_timestamp(zero + timedelta(minutes=5)),
        "mean": pytest.approx(14.915254237288135),
        "min": pytest.approx(10.0),
        "max": pytest.approx(20.0),
        "last_reset": None,
        "state": None,
        "sum": None,
    }
    expected_stats1 = [expected_1]
    expected_stats2 = [expected_1]

    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}

    # Insert metadata for sensor.test99
    metadata_1 = {
        "has_mean": True,
        "has_sum": False,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "sensor.test99",
        "unit_of_measurement": "kWh",
    }

    with session_scope(hass=hass) as session:
        session.add(recorder.db_schema.StatisticsMeta.from_meta(metadata_1))

    # Rename entity sensor.test1 to sensor.test99
    @callback
    def rename_entry():
        entity_reg.async_update_entity("sensor.test1", new_entity_id="sensor.test99")

    hass.add_job(rename_entry)
    wait_recording_done(hass)

    # Statistics failed to migrate due to the collision
    stats = statistics_during_period(hass, zero, period="5minute")
    assert stats == {"sensor.test1": expected_stats1, "sensor.test2": expected_stats2}
    assert "Blocked attempt to insert duplicated statistic rows" in caplog.text


def test_statistics_duplicated(hass_recorder, caplog):
    """Test statistics with same start time is not compiled."""
    hass = hass_recorder()
    setup_component(hass, "sensor", {})
    zero, four, states = record_states(hass)
    hist = history.get_significant_states(hass, zero, four)
    assert_dict_of_states_equal_without_context_and_last_changed(states, hist)

    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    with patch(
        "homeassistant.components.sensor.recorder.compile_statistics",
        return_value=statistics.PlatformCompiledStatistics([], {}),
    ) as compile_statistics:
        do_adhoc_statistics(hass, start=zero)
        wait_recording_done(hass)
        assert compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" in caplog.text
        assert "Statistics already compiled" not in caplog.text
        caplog.clear()

        do_adhoc_statistics(hass, start=zero)
        wait_recording_done(hass)
        assert not compile_statistics.called
        compile_statistics.reset_mock()
        assert "Compiling statistics for" not in caplog.text
        assert "Statistics already compiled" in caplog.text
        caplog.clear()


@pytest.mark.parametrize("last_reset_str", ("2022-01-01T00:00:00+02:00", None))
@pytest.mark.parametrize(
    "source, statistic_id, import_fn",
    (
        ("test", "test:total_energy_import", async_add_external_statistics),
        ("recorder", "sensor.total_energy_import", async_import_statistics),
    ),
)
async def test_import_statistics(
    recorder_mock,
    hass,
    hass_ws_client,
    caplog,
    source,
    statistic_id,
    import_fn,
    last_reset_str,
):
    """Test importing statistics and inserting external statistics."""
    client = await hass_ws_client()

    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = dt_util.parse_datetime(last_reset_str) if last_reset_str else None
    last_reset_utc = dt_util.as_utc(last_reset) if last_reset else None
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    period2 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    external_statistics1 = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }
    external_statistics2 = {
        "start": period2,
        "last_reset": last_reset,
        "state": 1,
        "sum": 3,
    }

    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": source,
        "statistic_id": statistic_id,
        "unit_of_measurement": "kWh",
    }

    import_fn(hass, external_metadata, (external_statistics1, external_statistics2))
    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1),
                "end": process_timestamp(period1 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(0.0),
                "sum": pytest.approx(2.0),
            },
            {
                "start": process_timestamp(period2),
                "end": process_timestamp(period2 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids=(statistic_id,))
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    last_stats = get_last_statistics(
        hass,
        1,
        statistic_id,
        True,
        {"last_reset", "max", "mean", "min", "state", "sum"},
    )
    assert last_stats == {
        statistic_id: [
            {
                "start": process_timestamp(period2),
                "end": process_timestamp(period2 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics
    external_statistics = {
        "start": period1,
        "last_reset": None,
        "state": 5,
        "sum": 6,
    }
    import_fn(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1),
                "end": process_timestamp(period1 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(5.0),
                "sum": pytest.approx(6.0),
            },
            {
                "start": process_timestamp(period2),
                "end": process_timestamp(period2 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Update the previously inserted statistics + rename
    external_statistics = {
        "start": period1,
        "max": 1,
        "mean": 2,
        "min": 3,
        "last_reset": last_reset,
        "state": 4,
        "sum": 5,
    }
    external_metadata["name"] = "Total imported energy renamed"
    import_fn(hass, external_metadata, (external_statistics,))
    await async_wait_recording_done(hass)
    statistic_ids = list_statistic_ids(hass)
    assert statistic_ids == [
        {
            "display_unit_of_measurement": "kWh",
            "has_mean": False,
            "has_sum": True,
            "statistic_id": statistic_id,
            "name": "Total imported energy renamed",
            "source": source,
            "statistics_unit_of_measurement": "kWh",
            "unit_class": "energy",
        }
    ]
    metadata = get_metadata(hass, statistic_ids=(statistic_id,))
    assert metadata == {
        statistic_id: (
            1,
            {
                "has_mean": False,
                "has_sum": True,
                "name": "Total imported energy renamed",
                "source": source,
                "statistic_id": statistic_id,
                "unit_of_measurement": "kWh",
            },
        )
    }
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1),
                "end": process_timestamp(period1 + timedelta(hours=1)),
                "max": pytest.approx(1.0),
                "mean": pytest.approx(2.0),
                "min": pytest.approx(3.0),
                "last_reset": last_reset_utc,
                "state": pytest.approx(4.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": process_timestamp(period2),
                "end": process_timestamp(period2 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
        ]
    }

    # Adjust the statistics in a different unit
    await client.send_json(
        {
            "id": 1,
            "type": "recorder/adjust_sum_statistics",
            "statistic_id": statistic_id,
            "start_time": period2.isoformat(),
            "adjustment": 1000.0,
            "adjustment_unit_of_measurement": "MWh",
        }
    )
    response = await client.receive_json()
    assert response["success"]

    await async_wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="hour")
    assert stats == {
        statistic_id: [
            {
                "start": process_timestamp(period1),
                "end": process_timestamp(period1 + timedelta(hours=1)),
                "max": pytest.approx(1.0),
                "mean": pytest.approx(2.0),
                "min": pytest.approx(3.0),
                "last_reset": last_reset_utc,
                "state": pytest.approx(4.0),
                "sum": pytest.approx(5.0),
            },
            {
                "start": process_timestamp(period2),
                "end": process_timestamp(period2 + timedelta(hours=1)),
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": last_reset_utc,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(1000 * 1000 + 3.0),
            },
        ]
    }


def test_external_statistics_errors(hass_recorder, caplog):
    """Test validation of external statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = zero.replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    _external_statistics = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }

    _external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    # Attempt to insert statistics for an entity
    external_metadata = {
        **_external_metadata,
        "statistic_id": "sensor.total_energy_import",
    }
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}

    # Attempt to insert statistics for the wrong domain
    external_metadata = {**_external_metadata, "source": "other"}
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics for a naive starting time
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "start": period1.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics for an invalid starting time
    external_metadata = {**_external_metadata}
    external_statistics = {**_external_statistics, "start": period1.replace(minute=1)}
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics with a naive last_reset
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "last_reset": last_reset.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_add_external_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}


def test_import_statistics_errors(hass_recorder, caplog):
    """Test validation of imported statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    last_reset = zero.replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    period1 = zero.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    _external_statistics = {
        "start": period1,
        "last_reset": last_reset,
        "state": 0,
        "sum": 2,
    }

    _external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "recorder",
        "statistic_id": "sensor.total_energy_import",
        "unit_of_measurement": "kWh",
    }

    # Attempt to insert statistics for an external source
    external_metadata = {
        **_external_metadata,
        "statistic_id": "test:total_energy_import",
    }
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("test:total_energy_import",)) == {}

    # Attempt to insert statistics for the wrong domain
    external_metadata = {**_external_metadata, "source": "sensor"}
    external_statistics = {**_external_statistics}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}

    # Attempt to insert statistics for a naive starting time
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "start": period1.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}

    # Attempt to insert statistics for an invalid starting time
    external_metadata = {**_external_metadata}
    external_statistics = {**_external_statistics, "start": period1.replace(minute=1)}
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}

    # Attempt to insert statistics with a naive last_reset
    external_metadata = {**_external_metadata}
    external_statistics = {
        **_external_statistics,
        "last_reset": last_reset.replace(tzinfo=None),
    }
    with pytest.raises(HomeAssistantError):
        async_import_statistics(hass, external_metadata, (external_statistics,))
    wait_recording_done(hass)
    assert statistics_during_period(hass, zero, period="hour") == {}
    assert list_statistic_ids(hass) == []
    assert get_metadata(hass, statistic_ids=("sensor.total_energy_import",)) == {}


@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2022-10-01 00:00:00+00:00")
def test_weekly_statistics(hass_recorder, caplog, timezone):
    """Test weekly statistics."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(timezone))

    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2022-10-09 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2022-10-16 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="week")
    week1_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-03 00:00:00"))
    week1_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_start = dt_util.as_utc(dt_util.parse_datetime("2022-10-10 00:00:00"))
    week2_end = dt_util.as_utc(dt_util.parse_datetime("2022-10-17 00:00:00"))
    assert stats == {
        "test:total_energy_import": [
            {
                "start": week1_start,
                "end": week1_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": 1.0,
                "sum": 3.0,
            },
            {
                "start": week2_start,
                "end": week2_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": 3.0,
                "sum": 5.0,
            },
        ]
    }

    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["not", "the", "same", "test:total_energy_import"],
        period="week",
    )
    assert stats == {
        "test:total_energy_import": [
            {
                "start": week1_start,
                "end": week1_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": 1.0,
                "sum": 3.0,
            },
            {
                "start": week2_start,
                "end": week2_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": 3.0,
                "sum": 5.0,
            },
        ]
    }

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="month"
    )
    assert stats == {}

    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))


@pytest.mark.parametrize("timezone", ["America/Regina", "Europe/Vienna", "UTC"])
@pytest.mark.freeze_time("2021-08-01 00:00:00+00:00")
def test_monthly_statistics(hass_recorder, caplog, timezone):
    """Test monthly statistics."""
    dt_util.set_default_time_zone(dt_util.get_time_zone(timezone))

    hass = hass_recorder()
    wait_recording_done(hass)
    assert "Compiling statistics for" not in caplog.text
    assert "Statistics already compiled" not in caplog.text

    zero = dt_util.utcnow()
    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))
    period3 = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    period4 = dt_util.as_utc(dt_util.parse_datetime("2021-10-31 23:00:00"))

    external_statistics = (
        {
            "start": period1,
            "last_reset": None,
            "state": 0,
            "sum": 2,
        },
        {
            "start": period2,
            "last_reset": None,
            "state": 1,
            "sum": 3,
        },
        {
            "start": period3,
            "last_reset": None,
            "state": 2,
            "sum": 4,
        },
        {
            "start": period4,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    )
    external_metadata = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import",
        "unit_of_measurement": "kWh",
    }

    async_add_external_statistics(hass, external_metadata, external_statistics)
    wait_recording_done(hass)
    stats = statistics_during_period(hass, zero, period="month")
    sep_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    sep_end = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_end = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    assert stats == {
        "test:total_energy_import": [
            {
                "start": sep_start,
                "end": sep_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
            {
                "start": oct_start,
                "end": oct_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(3.0),
                "sum": pytest.approx(5.0),
            },
        ]
    }

    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["not", "the", "same", "test:total_energy_import"],
        period="month",
    )
    sep_start = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    sep_end = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_start = dt_util.as_utc(dt_util.parse_datetime("2021-10-01 00:00:00"))
    oct_end = dt_util.as_utc(dt_util.parse_datetime("2021-11-01 00:00:00"))
    assert stats == {
        "test:total_energy_import": [
            {
                "start": sep_start,
                "end": sep_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(1.0),
                "sum": pytest.approx(3.0),
            },
            {
                "start": oct_start,
                "end": oct_end,
                "max": None,
                "mean": None,
                "min": None,
                "last_reset": None,
                "state": pytest.approx(3.0),
                "sum": pytest.approx(5.0),
            },
        ]
    }

    # Use 5minute to ensure table switch works
    stats = statistics_during_period(
        hass,
        start_time=zero,
        statistic_ids=["test:total_energy_import", "with_other"],
        period="5minute",
    )
    assert stats == {}

    # Ensure future date has not data
    future = dt_util.as_utc(dt_util.parse_datetime("2221-11-01 00:00:00"))
    stats = statistics_during_period(
        hass, start_time=future, end_time=future, period="month"
    )
    assert stats == {}

    dt_util.set_default_time_zone(dt_util.get_time_zone("UTC"))


def test_delete_duplicates_no_duplicates(hass_recorder, caplog):
    """Test removal of duplicated statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    with session_scope(hass=hass) as session:
        delete_statistics_duplicates(hass, session)
    assert "duplicated statistics rows" not in caplog.text
    assert "Found non identical" not in caplog.text
    assert "Found duplicated" not in caplog.text


def test_duplicate_statistics_handle_integrity_error(hass_recorder, caplog):
    """Test the recorder does not blow up if statistics is duplicated."""
    hass = hass_recorder()
    wait_recording_done(hass)

    period1 = dt_util.as_utc(dt_util.parse_datetime("2021-09-01 00:00:00"))
    period2 = dt_util.as_utc(dt_util.parse_datetime("2021-09-30 23:00:00"))

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_statistics_1 = [
        {
            "start": period1,
            "last_reset": None,
            "state": 3,
            "sum": 5,
        },
    ]
    external_energy_statistics_2 = [
        {
            "start": period2,
            "last_reset": None,
            "state": 3,
            "sum": 6,
        }
    ]

    with patch.object(
        statistics, "_statistics_exists", return_value=False
    ), patch.object(
        statistics, "_insert_statistics", wraps=statistics._insert_statistics
    ) as insert_statistics_mock:
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_1
        )
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_1
        )
        async_add_external_statistics(
            hass, external_energy_metadata_1, external_energy_statistics_2
        )
        wait_recording_done(hass)
        assert insert_statistics_mock.call_count == 3

    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.db_schema.Statistics).all()
        assert len(tmp) == 2

    assert "Blocked attempt to insert duplicated statistic rows" in caplog.text


def _create_engine_28(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]
    engine = create_engine(*args, **kwargs)
    old_db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
        )
        session.add(
            recorder.db_schema.SchemaChanges(
                schema_version=old_db_schema.SCHEMA_VERSION
            )
        )
        session.commit()
    return engine


def test_delete_metadata_duplicates(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics_meta with schema version 28
    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.core.create_engine", new=_create_engine_28
    ):
        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )

        with session_scope(hass=hass) as session:
            tmp = session.query(recorder.db_schema.StatisticsMeta).all()
            assert len(tmp) == 3
            assert tmp[0].id == 1
            assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
            assert tmp[1].id == 2
            assert tmp[1].statistic_id == "test:total_energy_import_tariff_1"
            assert tmp[2].id == 3
            assert tmp[2].statistic_id == "test:fossil_percentage"

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 28
    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    assert "Deleted 1 duplicated statistics_meta rows" in caplog.text
    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.db_schema.StatisticsMeta).all()
        assert len(tmp) == 2
        assert tmp[0].id == 2
        assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
        assert tmp[1].id == 3
        assert tmp[1].statistic_id == "test:fossil_percentage"

    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ


def test_delete_metadata_duplicates_many(caplog, tmpdir):
    """Test removal of duplicated statistics."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    module = "tests.components.recorder.db_schema_28"
    importlib.import_module(module)
    old_db_schema = sys.modules[module]

    external_energy_metadata_1 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_1",
        "unit_of_measurement": "kWh",
    }
    external_energy_metadata_2 = {
        "has_mean": False,
        "has_sum": True,
        "name": "Total imported energy",
        "source": "test",
        "statistic_id": "test:total_energy_import_tariff_2",
        "unit_of_measurement": "kWh",
    }
    external_co2_metadata = {
        "has_mean": True,
        "has_sum": False,
        "name": "Fossil percentage",
        "source": "test",
        "statistic_id": "test:fossil_percentage",
        "unit_of_measurement": "%",
    }

    # Create some duplicated statistics with schema version 28
    with patch.object(recorder, "db_schema", old_db_schema), patch.object(
        recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
    ), patch(
        "homeassistant.components.recorder.core.create_engine", new=_create_engine_28
    ):
        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_1)
            )
            for _ in range(3000):
                session.add(
                    recorder.db_schema.StatisticsMeta.from_meta(
                        external_energy_metadata_1
                    )
                )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_energy_metadata_2)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )
            session.add(
                recorder.db_schema.StatisticsMeta.from_meta(external_co2_metadata)
            )

        hass.stop()
        dt_util.DEFAULT_TIME_ZONE = ORIG_TZ

    # Test that the duplicates are removed during migration from schema 28
    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, "recorder", {"recorder": {"db_url": dburl}})
    hass.start()
    wait_recording_done(hass)
    wait_recording_done(hass)

    assert "Deleted 3002 duplicated statistics_meta rows" in caplog.text
    with session_scope(hass=hass) as session:
        tmp = session.query(recorder.db_schema.StatisticsMeta).all()
        assert len(tmp) == 3
        assert tmp[0].id == 3001
        assert tmp[0].statistic_id == "test:total_energy_import_tariff_1"
        assert tmp[1].id == 3003
        assert tmp[1].statistic_id == "test:total_energy_import_tariff_2"
        assert tmp[2].id == 3005
        assert tmp[2].statistic_id == "test:fossil_percentage"

    hass.stop()
    dt_util.DEFAULT_TIME_ZONE = ORIG_TZ


def test_delete_metadata_duplicates_no_duplicates(hass_recorder, caplog):
    """Test removal of duplicated statistics."""
    hass = hass_recorder()
    wait_recording_done(hass)
    with session_scope(hass=hass) as session:
        delete_statistics_meta_duplicates(session)
    assert "duplicated statistics_meta rows" not in caplog.text


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize("db_engine", ("mysql", "postgresql"))
async def test_validate_db_schema(
    async_setup_recorder_instance, hass, caplog, db_engine
):
    """Test validating DB schema with MySQL and PostgreSQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)
    assert "Schema validation failed" not in caplog.text
    assert "Detected statistics schema errors" not in caplog.text
    assert "Database is about to correct DB schema errors" not in caplog.text


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
async def test_validate_db_schema_fix_utf8_issue(
    async_setup_recorder_instance, hass, caplog
):
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    utf8_error = OperationalError("", "", orig=orig_error)
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", "mysql"
    ), patch(
        "homeassistant.components.recorder.statistics._update_or_add_metadata",
        side_effect=[utf8_error, DEFAULT, DEFAULT],
        wraps=_update_or_add_metadata,
    ):
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        "Database is about to correct DB schema errors: statistics_meta.4-byte UTF-8"
        in caplog.text
    )
    assert (
        "Updating character set and collation of table statistics_meta to utf8mb4"
        in caplog.text
    )


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize("db_engine", ("mysql", "postgresql"))
@pytest.mark.parametrize(
    "table, replace_index", (("statistics", 0), ("statistics_short_term", 1))
)
@pytest.mark.parametrize(
    "column, value",
    (("max", 1.0), ("mean", 1.0), ("min", 1.0), ("state", 1.0), ("sum", 1.0)),
)
async def test_validate_db_schema_fix_float_issue(
    async_setup_recorder_instance,
    hass,
    caplog,
    db_engine,
    table,
    replace_index,
    column,
    value,
):
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    precise_number = 1.000000000000001
    precise_time = datetime(2020, 10, 6, microsecond=1, tzinfo=dt_util.UTC)
    statistics = {
        "recorder.db_test": [
            {
                "last_reset": precise_time,
                "max": precise_number,
                "mean": precise_number,
                "min": precise_number,
                "start": precise_time,
                "state": precise_number,
                "sum": precise_number,
            }
        ]
    }
    statistics["recorder.db_test"][0][column] = value
    fake_statistics = [DEFAULT, DEFAULT]
    fake_statistics[replace_index] = statistics

    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ), patch(
        "homeassistant.components.recorder.statistics._statistics_during_period_with_session",
        side_effect=fake_statistics,
        wraps=_statistics_during_period_with_session,
    ), patch(
        "homeassistant.components.recorder.migration._modify_columns"
    ) as modify_columns_mock:
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        f"Database is about to correct DB schema errors: {table}.double precision"
        in caplog.text
    )
    modification = [
        "mean DOUBLE PRECISION",
        "min DOUBLE PRECISION",
        "max DOUBLE PRECISION",
        "state DOUBLE PRECISION",
        "sum DOUBLE PRECISION",
    ]
    modify_columns_mock.assert_called_once_with(ANY, ANY, table, modification)


@pytest.mark.parametrize("enable_statistics_table_validation", [True])
@pytest.mark.parametrize(
    "db_engine, modification",
    (
        ("mysql", ["last_reset DATETIME(6)", "start DATETIME(6)"]),
        (
            "postgresql",
            [
                "last_reset TIMESTAMP(6) WITH TIME ZONE",
                "start TIMESTAMP(6) WITH TIME ZONE",
            ],
        ),
    ),
)
@pytest.mark.parametrize(
    "table, replace_index", (("statistics", 0), ("statistics_short_term", 1))
)
@pytest.mark.parametrize(
    "column, value",
    (
        ("last_reset", "2020-10-06T00:00:00+00:00"),
        ("start", "2020-10-06T00:00:00+00:00"),
    ),
)
async def test_validate_db_schema_fix_statistics_datetime_issue(
    async_setup_recorder_instance,
    hass,
    caplog,
    db_engine,
    modification,
    table,
    replace_index,
    column,
    value,
):
    """Test validating DB schema with MySQL.

    Note: The test uses SQLite, the purpose is only to exercise the code.
    """
    orig_error = MagicMock()
    orig_error.args = [1366]
    precise_number = 1.000000000000001
    precise_time = datetime(2020, 10, 6, microsecond=1, tzinfo=dt_util.UTC)
    statistics = {
        "recorder.db_test": [
            {
                "last_reset": precise_time,
                "max": precise_number,
                "mean": precise_number,
                "min": precise_number,
                "start": precise_time,
                "state": precise_number,
                "sum": precise_number,
            }
        ]
    }
    statistics["recorder.db_test"][0][column] = value
    fake_statistics = [DEFAULT, DEFAULT]
    fake_statistics[replace_index] = statistics

    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name", db_engine
    ), patch(
        "homeassistant.components.recorder.statistics._statistics_during_period_with_session",
        side_effect=fake_statistics,
        wraps=_statistics_during_period_with_session,
    ), patch(
        "homeassistant.components.recorder.migration._modify_columns"
    ) as modify_columns_mock:
        await async_setup_recorder_instance(hass)
        await async_wait_recording_done(hass)

    assert "Schema validation failed" not in caplog.text
    assert (
        f"Database is about to correct DB schema errors: {table}.µs precision"
        in caplog.text
    )
    modify_columns_mock.assert_called_once_with(ANY, ANY, table, modification)


def record_states(hass):
    """Record some test states.

    We inject a bunch of state updates temperature sensors.
    """
    mp = "media_player.test"
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns4 = "sensor.test4"
    sns1_attr = {
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }
    sns2_attr = {
        "device_class": "humidity",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }
    sns3_attr = {"device_class": "temperature"}
    sns4_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=15 * 5)
    three = two + timedelta(seconds=30 * 5)
    four = three + timedelta(seconds=15 * 5)

    states = {mp: [], sns1: [], sns2: [], sns3: [], sns4: []}
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=one
    ):
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "10", attributes=sns4_attr))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=two
    ):
        states[sns1].append(set_state(sns1, "15", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "15", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "15", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "15", attributes=sns4_attr))

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=three
    ):
        states[sns1].append(set_state(sns1, "20", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "20", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "20", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "20", attributes=sns4_attr))

    return zero, four, states

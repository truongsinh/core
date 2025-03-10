"""Test Home Assistant color util methods."""
import pytest
import voluptuous as vol

import homeassistant.util.color as color_util

GAMUT = color_util.GamutType(
    color_util.XYPoint(0.704, 0.296),
    color_util.XYPoint(0.2151, 0.7106),
    color_util.XYPoint(0.138, 0.08),
)
GAMUT_INVALID_1 = color_util.GamutType(
    color_util.XYPoint(0.704, 0.296),
    color_util.XYPoint(-0.201, 0.7106),
    color_util.XYPoint(0.138, 0.08),
)
GAMUT_INVALID_2 = color_util.GamutType(
    color_util.XYPoint(0.704, 1.296),
    color_util.XYPoint(0.2151, 0.7106),
    color_util.XYPoint(0.138, 0.08),
)
GAMUT_INVALID_3 = color_util.GamutType(
    color_util.XYPoint(0.0, 0.0),
    color_util.XYPoint(0.0, 0.0),
    color_util.XYPoint(0.0, 0.0),
)
GAMUT_INVALID_4 = color_util.GamutType(
    color_util.XYPoint(0.1, 0.1),
    color_util.XYPoint(0.3, 0.3),
    color_util.XYPoint(0.7, 0.7),
)


# pylint: disable=invalid-name
def test_color_RGB_to_xy_brightness():
    """Test color_RGB_to_xy_brightness."""
    assert color_util.color_RGB_to_xy_brightness(0, 0, 0) == (0, 0, 0)
    assert color_util.color_RGB_to_xy_brightness(255, 255, 255) == (0.323, 0.329, 255)

    assert color_util.color_RGB_to_xy_brightness(0, 0, 255) == (0.136, 0.04, 12)

    assert color_util.color_RGB_to_xy_brightness(0, 255, 0) == (0.172, 0.747, 170)

    assert color_util.color_RGB_to_xy_brightness(255, 0, 0) == (0.701, 0.299, 72)

    assert color_util.color_RGB_to_xy_brightness(128, 0, 0) == (0.701, 0.299, 16)

    assert color_util.color_RGB_to_xy_brightness(255, 0, 0, GAMUT) == (0.7, 0.299, 72)

    assert color_util.color_RGB_to_xy_brightness(0, 255, 0, GAMUT) == (
        0.215,
        0.711,
        170,
    )

    assert color_util.color_RGB_to_xy_brightness(0, 0, 255, GAMUT) == (0.138, 0.08, 12)


def test_color_RGB_to_xy():
    """Test color_RGB_to_xy."""
    assert color_util.color_RGB_to_xy(0, 0, 0) == (0, 0)
    assert color_util.color_RGB_to_xy(255, 255, 255) == (0.323, 0.329)

    assert color_util.color_RGB_to_xy(0, 0, 255) == (0.136, 0.04)

    assert color_util.color_RGB_to_xy(0, 255, 0) == (0.172, 0.747)

    assert color_util.color_RGB_to_xy(255, 0, 0) == (0.701, 0.299)

    assert color_util.color_RGB_to_xy(128, 0, 0) == (0.701, 0.299)

    assert color_util.color_RGB_to_xy(0, 0, 255, GAMUT) == (0.138, 0.08)

    assert color_util.color_RGB_to_xy(0, 255, 0, GAMUT) == (0.215, 0.711)

    assert color_util.color_RGB_to_xy(255, 0, 0, GAMUT) == (0.7, 0.299)


def test_color_xy_brightness_to_RGB():
    """Test color_xy_brightness_to_RGB."""
    assert color_util.color_xy_brightness_to_RGB(1, 1, 0) == (0, 0, 0)

    assert color_util.color_xy_brightness_to_RGB(0.35, 0.35, 128) == (194, 186, 169)

    assert color_util.color_xy_brightness_to_RGB(0.35, 0.35, 255) == (255, 243, 222)

    assert color_util.color_xy_brightness_to_RGB(1, 0, 255) == (255, 0, 60)

    assert color_util.color_xy_brightness_to_RGB(0, 1, 255) == (0, 255, 0)

    assert color_util.color_xy_brightness_to_RGB(0, 0, 255) == (0, 63, 255)

    assert color_util.color_xy_brightness_to_RGB(1, 0, 255, GAMUT) == (255, 0, 3)

    assert color_util.color_xy_brightness_to_RGB(0, 1, 255, GAMUT) == (82, 255, 0)

    assert color_util.color_xy_brightness_to_RGB(0, 0, 255, GAMUT) == (9, 85, 255)


def test_color_xy_to_RGB():
    """Test color_xy_to_RGB."""
    assert color_util.color_xy_to_RGB(0.35, 0.35) == (255, 243, 222)

    assert color_util.color_xy_to_RGB(1, 0) == (255, 0, 60)

    assert color_util.color_xy_to_RGB(0, 1) == (0, 255, 0)

    assert color_util.color_xy_to_RGB(0, 0) == (0, 63, 255)

    assert color_util.color_xy_to_RGB(1, 0, GAMUT) == (255, 0, 3)

    assert color_util.color_xy_to_RGB(0, 1, GAMUT) == (82, 255, 0)

    assert color_util.color_xy_to_RGB(0, 0, GAMUT) == (9, 85, 255)


def test_color_RGB_to_hsv():
    """Test color_RGB_to_hsv."""
    assert color_util.color_RGB_to_hsv(0, 0, 0) == (0, 0, 0)

    assert color_util.color_RGB_to_hsv(255, 255, 255) == (0, 0, 100)

    assert color_util.color_RGB_to_hsv(0, 0, 255) == (240, 100, 100)

    assert color_util.color_RGB_to_hsv(0, 255, 0) == (120, 100, 100)

    assert color_util.color_RGB_to_hsv(255, 0, 0) == (0, 100, 100)


def test_color_hsv_to_RGB():
    """Test color_hsv_to_RGB."""
    assert color_util.color_hsv_to_RGB(0, 0, 0) == (0, 0, 0)

    assert color_util.color_hsv_to_RGB(0, 0, 100) == (255, 255, 255)

    assert color_util.color_hsv_to_RGB(240, 100, 100) == (0, 0, 255)

    assert color_util.color_hsv_to_RGB(120, 100, 100) == (0, 255, 0)

    assert color_util.color_hsv_to_RGB(0, 100, 100) == (255, 0, 0)


def test_color_hsb_to_RGB():
    """Test color_hsb_to_RGB."""
    assert color_util.color_hsb_to_RGB(0, 0, 0) == (0, 0, 0)

    assert color_util.color_hsb_to_RGB(0, 0, 1.0) == (255, 255, 255)

    assert color_util.color_hsb_to_RGB(240, 1.0, 1.0) == (0, 0, 255)

    assert color_util.color_hsb_to_RGB(120, 1.0, 1.0) == (0, 255, 0)

    assert color_util.color_hsb_to_RGB(0, 1.0, 1.0) == (255, 0, 0)


def test_color_xy_to_hs():
    """Test color_xy_to_hs."""
    assert color_util.color_xy_to_hs(1, 1) == (47.294, 100)

    assert color_util.color_xy_to_hs(0.35, 0.35) == (38.182, 12.941)

    assert color_util.color_xy_to_hs(1, 0) == (345.882, 100)

    assert color_util.color_xy_to_hs(0, 1) == (120, 100)

    assert color_util.color_xy_to_hs(0, 0) == (225.176, 100)

    assert color_util.color_xy_to_hs(1, 0, GAMUT) == (359.294, 100)

    assert color_util.color_xy_to_hs(0, 1, GAMUT) == (100.706, 100)

    assert color_util.color_xy_to_hs(0, 0, GAMUT) == (221.463, 96.471)


def test_color_hs_to_xy():
    """Test color_hs_to_xy."""
    assert color_util.color_hs_to_xy(180, 100) == (0.151, 0.343)

    assert color_util.color_hs_to_xy(350, 12.5) == (0.356, 0.321)

    assert color_util.color_hs_to_xy(140, 50) == (0.229, 0.474)

    assert color_util.color_hs_to_xy(0, 40) == (0.474, 0.317)

    assert color_util.color_hs_to_xy(360, 0) == (0.323, 0.329)

    assert color_util.color_hs_to_xy(0, 100, GAMUT) == (0.7, 0.299)

    assert color_util.color_hs_to_xy(120, 100, GAMUT) == (0.215, 0.711)

    assert color_util.color_hs_to_xy(180, 100, GAMUT) == (0.17, 0.34)

    assert color_util.color_hs_to_xy(240, 100, GAMUT) == (0.138, 0.08)

    assert color_util.color_hs_to_xy(360, 100, GAMUT) == (0.7, 0.299)


def test_rgb_hex_to_rgb_list():
    """Test rgb_hex_to_rgb_list."""
    assert [255, 255, 255] == color_util.rgb_hex_to_rgb_list("ffffff")

    assert [0, 0, 0] == color_util.rgb_hex_to_rgb_list("000000")

    assert [255, 255, 255, 255] == color_util.rgb_hex_to_rgb_list("ffffffff")

    assert [0, 0, 0, 0] == color_util.rgb_hex_to_rgb_list("00000000")

    assert [51, 153, 255] == color_util.rgb_hex_to_rgb_list("3399ff")

    assert [51, 153, 255, 0] == color_util.rgb_hex_to_rgb_list("3399ff00")


def test_color_name_to_rgb_valid_name():
    """Test color_name_to_rgb."""
    assert color_util.color_name_to_rgb("red") == (255, 0, 0)

    assert color_util.color_name_to_rgb("blue") == (0, 0, 255)

    assert color_util.color_name_to_rgb("green") == (0, 128, 0)

    # spaces in the name
    assert color_util.color_name_to_rgb("dark slate blue") == (72, 61, 139)

    # spaces removed from name
    assert color_util.color_name_to_rgb("darkslateblue") == (72, 61, 139)
    assert color_util.color_name_to_rgb("dark slateblue") == (72, 61, 139)
    assert color_util.color_name_to_rgb("darkslate blue") == (72, 61, 139)


def test_color_name_to_rgb_unknown_name_raises_value_error():
    """Test color_name_to_rgb."""
    with pytest.raises(ValueError):
        color_util.color_name_to_rgb("not a color")


def test_color_rgb_to_rgbw():
    """Test color_rgb_to_rgbw."""
    assert color_util.color_rgb_to_rgbw(0, 0, 0) == (0, 0, 0, 0)

    assert color_util.color_rgb_to_rgbw(255, 255, 255) == (0, 0, 0, 255)

    assert color_util.color_rgb_to_rgbw(255, 0, 0) == (255, 0, 0, 0)

    assert color_util.color_rgb_to_rgbw(0, 255, 0) == (0, 255, 0, 0)

    assert color_util.color_rgb_to_rgbw(0, 0, 255) == (0, 0, 255, 0)

    assert color_util.color_rgb_to_rgbw(255, 127, 0) == (255, 127, 0, 0)

    assert color_util.color_rgb_to_rgbw(255, 127, 127) == (255, 0, 0, 253)

    assert color_util.color_rgb_to_rgbw(127, 127, 127) == (0, 0, 0, 127)


def test_color_rgbw_to_rgb():
    """Test color_rgbw_to_rgb."""
    assert color_util.color_rgbw_to_rgb(0, 0, 0, 0) == (0, 0, 0)

    assert color_util.color_rgbw_to_rgb(0, 0, 0, 255) == (255, 255, 255)

    assert color_util.color_rgbw_to_rgb(255, 0, 0, 0) == (255, 0, 0)

    assert color_util.color_rgbw_to_rgb(0, 255, 0, 0) == (0, 255, 0)

    assert color_util.color_rgbw_to_rgb(0, 0, 255, 0) == (0, 0, 255)

    assert color_util.color_rgbw_to_rgb(255, 127, 0, 0) == (255, 127, 0)

    assert color_util.color_rgbw_to_rgb(255, 0, 0, 253) == (255, 127, 127)

    assert color_util.color_rgbw_to_rgb(0, 0, 0, 127) == (127, 127, 127)


def test_color_rgb_to_hex():
    """Test color_rgb_to_hex."""
    assert color_util.color_rgb_to_hex(255, 255, 255) == "ffffff"
    assert color_util.color_rgb_to_hex(0, 0, 0) == "000000"
    assert color_util.color_rgb_to_hex(51, 153, 255) == "3399ff"
    assert color_util.color_rgb_to_hex(255, 67.9204190, 0) == "ff4400"


def test_match_max_scale():
    """Test match_max_scale."""
    match_max_scale = color_util.match_max_scale
    assert match_max_scale((255, 255, 255), (255, 255, 255)) == (255, 255, 255)
    assert match_max_scale((0, 0, 0), (0, 0, 0)) == (0, 0, 0)
    assert match_max_scale((255, 255, 255), (128, 128, 128)) == (255, 255, 255)
    assert match_max_scale((0, 255, 0), (64, 128, 128)) == (128, 255, 255)
    assert match_max_scale((0, 100, 0), (128, 64, 64)) == (100, 50, 50)
    assert match_max_scale((10, 20, 33), (100, 200, 333)) == (10, 20, 33)
    assert match_max_scale((255,), (100, 200, 333)) == (77, 153, 255)
    assert match_max_scale((128,), (10.5, 20.9, 30.4)) == (44, 88, 128)
    assert match_max_scale((10, 20, 30, 128), (100, 200, 333)) == (38, 77, 128)


def test_gamut():
    """Test gamut functions."""
    assert color_util.check_valid_gamut(GAMUT)
    assert not color_util.check_valid_gamut(GAMUT_INVALID_1)
    assert not color_util.check_valid_gamut(GAMUT_INVALID_2)
    assert not color_util.check_valid_gamut(GAMUT_INVALID_3)
    assert not color_util.check_valid_gamut(GAMUT_INVALID_4)


def test_color_temperature_mired_to_kelvin():
    """Test color_temperature_mired_to_kelvin."""
    assert color_util.color_temperature_mired_to_kelvin(40) == 25000
    assert color_util.color_temperature_mired_to_kelvin(200) == 5000
    with pytest.raises(ZeroDivisionError):
        assert color_util.color_temperature_mired_to_kelvin(0)


def test_color_temperature_kelvin_to_mired():
    """Test color_temperature_kelvin_to_mired."""
    assert color_util.color_temperature_kelvin_to_mired(25000) == 40
    assert color_util.color_temperature_kelvin_to_mired(5000) == 200
    with pytest.raises(ZeroDivisionError):
        assert color_util.color_temperature_kelvin_to_mired(0)


def test_returns_same_value_for_any_two_temperatures_below_1000():
    """Function should return same value for 999 Kelvin and 0 Kelvin."""
    rgb_1 = color_util.color_temperature_to_rgb(999)
    rgb_2 = color_util.color_temperature_to_rgb(0)
    assert rgb_1 == rgb_2


def test_returns_same_value_for_any_two_temperatures_above_40000():
    """Function should return same value for 40001K and 999999K."""
    rgb_1 = color_util.color_temperature_to_rgb(40001)
    rgb_2 = color_util.color_temperature_to_rgb(999999)
    assert rgb_1 == rgb_2


def test_should_return_pure_white_at_6600():
    """Function should return red=255, blue=255, green=255 when given 6600K.

    6600K is considered "pure white" light.
    This is just a rough estimate because the formula itself is a "best
    guess" approach.
    """
    rgb = color_util.color_temperature_to_rgb(6600)
    assert rgb == (255, 255, 255)


def test_color_above_6600_should_have_more_blue_than_red_or_green():
    """Function should return a higher blue value for blue-ish light."""
    rgb = color_util.color_temperature_to_rgb(6700)
    assert rgb[2] > rgb[1]
    assert rgb[2] > rgb[0]


def test_color_below_6600_should_have_more_red_than_blue_or_green():
    """Function should return a higher red value for red-ish light."""
    rgb = color_util.color_temperature_to_rgb(6500)
    assert rgb[0] > rgb[1]
    assert rgb[0] > rgb[2]


def test_get_color_in_voluptuous():
    """Test using the get method in color validation."""
    schema = vol.Schema(color_util.color_name_to_rgb)

    with pytest.raises(vol.Invalid):
        schema("not a color")

    assert schema("red") == (255, 0, 0)


def test_color_rgb_to_rgbww():
    """Test color_rgb_to_rgbww conversions."""
    # Light with mid point at ~4600K (warm white) -> output compensated by adding blue
    assert color_util.color_rgb_to_rgbww(255, 255, 255, 2702, 6493) == (
        0,
        54,
        98,
        255,
        255,
    )
    # Light with mid point at ~5500K (less warm white) -> output compensated by adding less blue
    assert color_util.color_rgb_to_rgbww(255, 255, 255, 1000, 10000) == (
        255,
        255,
        255,
        0,
        0,
    )
    # Light with mid point at ~1MK (unrealistically cold white) -> output compensated by adding red
    assert color_util.color_rgb_to_rgbww(255, 255, 255, 1000, 1000000) == (
        0,
        118,
        241,
        255,
        255,
    )
    assert color_util.color_rgb_to_rgbww(128, 128, 128, 2702, 6493) == (
        0,
        27,
        49,
        128,
        128,
    )
    assert color_util.color_rgb_to_rgbww(64, 64, 64, 2702, 6493) == (0, 14, 25, 64, 64)
    assert color_util.color_rgb_to_rgbww(32, 64, 16, 2702, 6493) == (9, 64, 0, 38, 38)
    assert color_util.color_rgb_to_rgbww(0, 0, 0, 2702, 6493) == (0, 0, 0, 0, 0)
    assert color_util.color_rgb_to_rgbww(0, 0, 0, 10000, 1000000) == (0, 0, 0, 0, 0)
    assert color_util.color_rgb_to_rgbww(255, 255, 255, 200000, 1000000) == (
        103,
        69,
        0,
        255,
        255,
    )


def test_color_rgbww_to_rgb():
    """Test color_rgbww_to_rgb conversions."""
    assert color_util.color_rgbww_to_rgb(0, 54, 98, 255, 255, 2702, 6493) == (
        255,
        255,
        255,
    )
    # rgb fully on, + both white channels turned off -> rgb fully on
    assert color_util.color_rgbww_to_rgb(255, 255, 255, 0, 0, 2702, 6493) == (
        255,
        255,
        255,
    )
    # r < g < b + both white channels fully enabled -> r < g < b capped at 255
    assert color_util.color_rgbww_to_rgb(0, 118, 241, 255, 255, 2702, 6493) == (
        163,
        204,
        255,
    )
    # r < g < b + both white channels 50% enabled -> r < g < b capped at 128
    assert color_util.color_rgbww_to_rgb(0, 27, 49, 128, 128, 2702, 6493) == (
        128,
        128,
        128,
    )
    # r < g < b + both white channels 25% enabled -> r < g < b capped at 64
    assert color_util.color_rgbww_to_rgb(0, 14, 25, 64, 64, 2702, 6493) == (64, 64, 64)
    assert color_util.color_rgbww_to_rgb(9, 64, 0, 38, 38, 2702, 6493) == (32, 64, 16)
    assert color_util.color_rgbww_to_rgb(0, 0, 0, 0, 0, 2702, 6493) == (0, 0, 0)
    assert color_util.color_rgbww_to_rgb(103, 69, 0, 255, 255, 2702, 6535) == (
        255,
        193,
        112,
    )


def test_color_temperature_to_rgbww():
    """Test color temp to warm, cold conversion.

    Temperature values must be in mireds
    Home Assistant uses rgbcw for rgbww
    """
    # Coldest color temperature -> only cold channel enabled
    assert color_util.color_temperature_to_rgbww(6535, 255, 2000, 6535) == (
        0,
        0,
        0,
        255,
        0,
    )
    assert color_util.color_temperature_to_rgbww(6535, 128, 2000, 6535) == (
        0,
        0,
        0,
        128,
        0,
    )
    # Warmest color temperature -> only cold channel enabled
    assert color_util.color_temperature_to_rgbww(2000, 255, 2000, 6535) == (
        0,
        0,
        0,
        0,
        255,
    )
    assert color_util.color_temperature_to_rgbww(2000, 128, 2000, 6535) == (
        0,
        0,
        0,
        0,
        128,
    )
    # Warmer than mid point color temperature -> More warm than cold channel enabled
    assert color_util.color_temperature_to_rgbww(2881, 255, 2000, 6535) == (
        0,
        0,
        0,
        112,
        143,
    )
    assert color_util.color_temperature_to_rgbww(2881, 128, 2000, 6535) == (
        0,
        0,
        0,
        56,
        72,
    )


def test_rgbww_to_color_temperature():
    """Test rgbww conversion to color temp.

    Temperature values must be in mireds
    Home Assistant uses rgbcw for rgbww
    """
    # Only cold channel enabled -> coldest color temperature
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 255, 0), 2000, 6535) == (
        6535,
        255,
    )
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 128, 0), 2000, 6535) == (
        6535,
        128,
    )
    # Only warm channel enabled -> warmest color temperature
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 0, 255), 2000, 6535) == (
        2000,
        255,
    )
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 0, 128), 2000, 6535) == (
        2000,
        128,
    )
    # More warm than cold channel enabled -> warmer than mid point
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 112, 143), 2000, 6535) == (
        2876,
        255,
    )
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 56, 72), 2000, 6535) == (
        2872,
        128,
    )
    # Both channels turned off -> warmest color temperature
    assert color_util.rgbww_to_color_temperature((0, 0, 0, 0, 0), 2000, 6535) == (
        2000,
        0,
    )


def test_white_levels_to_color_temperature():
    """Test warm, cold conversion to color temp.

    Temperature values must be in mireds
    Home Assistant uses rgbcw for rgbww
    """
    # Only cold channel enabled -> coldest color temperature
    assert color_util._white_levels_to_color_temperature(255, 0, 2000, 6535) == (
        6535,
        255,
    )
    assert color_util._white_levels_to_color_temperature(128, 0, 2000, 6535) == (
        6535,
        128,
    )
    # Only warm channel enabled -> warmest color temperature
    assert color_util._white_levels_to_color_temperature(0, 255, 2000, 6535) == (
        2000,
        255,
    )
    assert color_util._white_levels_to_color_temperature(0, 128, 2000, 6535) == (
        2000,
        128,
    )
    assert color_util._white_levels_to_color_temperature(112, 143, 2000, 6535) == (
        2876,
        255,
    )
    assert color_util._white_levels_to_color_temperature(56, 72, 2000, 6535) == (
        2872,
        128,
    )
    # Both channels turned off -> warmest color temperature
    assert color_util._white_levels_to_color_temperature(0, 0, 2000, 6535) == (
        2000,
        0,
    )

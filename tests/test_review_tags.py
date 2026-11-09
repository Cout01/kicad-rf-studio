# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import replace
from pathlib import Path

from kicad_rf_studio.core.kicad import classify, load_board
from kicad_rf_studio.core.review.planes import plane_nets
from kicad_rf_studio.core.review.tags import family, tag
from test_review_planes import dotted

FIX = Path(__file__).parent / "fixtures"


def test_the_name_patterns_tag_a8s_families_past_the_deny_list():  # design 5.1, 6
    names = ["SWDIO", "SPI_CS", "CLK_GEN", "LORA_DIO1", "MCU_D+", "MCU_D-", "USB_D+", "QSPI_CLK", "SPI1_SCK",
             "XTAL_IN", "BUCK_SW", "I2S_BCLK", "SPI_MOSI", "/MCU/SCK", "CLK_EN", "SW1", "spi_cs2"]
    assert {n: family(n) for n in names} == {
        "SWDIO": None, "SPI_CS": None, "CLK_GEN": "CLK", "LORA_DIO1": None, "MCU_D+": None, "MCU_D-": None,
        "USB_D+": "USB", "QSPI_CLK": "CLK", "SPI1_SCK": "SCK", "XTAL_IN": "XTAL", "BUCK_SW": "SW",
        "I2S_BCLK": "CLK", "SPI_MOSI": "SPI", "/MCU/SCK": "SCK", "CLK_EN": None, "SW1": "SW", "spi_cs2": None}


def usb(edit=lambda b: None):
    b = load_board(FIX / "usb2_hs.kicad_pcb")
    edit(b)
    c = classify(b)
    return b, c, plane_nets(b, c)


def test_patterns_tag_a_board_with_no_flag_and_the_walk_reaches_behind_its_resistors():  # design 5.1; BC2
    assert tag(*usb()) == ({"MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "pattern:USB", "USB_D-": "pattern:USB"}, [])
    b = load_board(FIX / "qspi_clk.kicad_pcb")
    c = classify(b)
    assert tag(b, c, plane_nets(b, c))[0] == {"FLASH_CLK": "pattern:CLK", "QSPI_CLK": "pattern:CLK"}


def test_flags_replace_the_patterns_a_project_adds_and_ground_and_power_are_never_tagged():  # design 5.1; BC2
    b, c, never = usb()
    assert tag(b, c, never, ["AUX"]) == ({"AUX": "flag"}, [])
    assert tag(b, c, never, ["USB_D*", "NOPE"]) == (
        {"MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "flag", "USB_D-": "flag"}, ["NOPE"])
    assert set(tag(b, c, never, ["*"])[0]) == {"AUX", "MCU_D+", "MCU_D-", "USB_D+", "USB_D-"}  # no GND, +3V3, VBUS
    assert tag(b, c, never, ["GND"]) == ({}, ["GND"])  # a flag of ground or power names nothing the review tags
    assert "+3.3V" not in tag(*usb(dotted), ["*"])[0]  # a dotted supply is a plane net, so never tagged
    assert tag(b, c, never, chain_nets=["AUX", "USB_D+"])[0] == {
        "AUX": "project", "MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "project", "USB_D-": "pattern:USB"}
    assert tag(b, c, never, ["AUX"], ["USB_D+"])[0] == {
        "AUX": "flag", "MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "project", "USB_D-": "walk"}


def pull_ups(b):  # R2 and C1 as pull-ups to a dotted +3.3V, which tracer.POWER and so _links do not block
    dotted(b)
    for ref, nets in (("R2", ("MCU_D+", "+3.3V")), ("C1", ("+3.3V", "AUX"))):
        fp = b.footprints[ref]
        b.footprints[ref] = replace(fp, pads=tuple(replace(p, net=n) for p, n in zip(fp.pads, nets)))


def test_the_walk_never_passes_through_a_dotted_supply():  # design 5.1; plan Task 3 step 3
    assert tag(*usb(pull_ups), ["USB_D+"])[0] == {
        "MCU_D+": "walk", "MCU_D-": "walk", "USB_D+": "flag", "USB_D-": "walk"}  # no AUX past the supply

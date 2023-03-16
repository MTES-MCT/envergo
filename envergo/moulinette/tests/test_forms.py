import pytest

from envergo.moulinette.forms import MoulinetteForm


def test_total_surface_is_inferred():
    data = {
        "created_surface": 50,
        "existing_surface": 50,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }

    form = MoulinetteForm(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "project_surface" in data
    assert data["project_surface"] == 100


def test_existing_surface_is_inferred():
    data = {
        "created_surface": 50,
        "project_surface": 100,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }

    form = MoulinetteForm(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "existing_surface" in data
    assert data["existing_surface"] == 50


def test_existing_surface_or_project_surface_is_required():
    data = {
        "created_surface": 50,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }

    form = MoulinetteForm(data)
    assert not form.is_valid()
    assert "project_surface" in form.errors


def test_existing_surface_can_be_zero():
    data = {
        "created_surface": 50,
        "existing_surface": 0,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }

    form = MoulinetteForm(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "project_surface" in data
    assert data["project_surface"] == 50


def test_total_surface_must_be_correct():
    data = {
        "created_surface": 50,
        "existing_surface": 60,
        "project_surface": 110,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    form = MoulinetteForm(data)
    assert form.is_valid()

    data["project_surface"] = 100
    form = MoulinetteForm(data)
    assert not form.is_valid()
    assert "project_surface" in form.errors


def test_existing_surface_cannot_be_negative():
    data = {
        "created_surface": 50,
        "project_surface": 40,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }

    form = MoulinetteForm(data)
    assert not form.is_valid()
    assert "project_surface" in form.errors

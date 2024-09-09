from envergo.moulinette.forms import MoulinetteFormAmenagement
from envergo.moulinette.utils import compute_surfaces


def test_total_surface_is_inferred():
    data = {
        "created_surface": 50,
        "existing_surface": 50,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    data.update(compute_surfaces(data))

    form = MoulinetteFormAmenagement(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "final_surface" in data
    assert data["final_surface"] == 100


def test_existing_surface_is_inferred():
    data = {
        "created_surface": 50,
        "final_surface": 100,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    data.update(compute_surfaces(data))

    form = MoulinetteFormAmenagement(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "existing_surface" in data
    assert data["existing_surface"] == 50


def test_existing_surface_or_final_surface_is_required():
    data = {
        "created_surface": 50,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    data.update(compute_surfaces(data))

    form = MoulinetteFormAmenagement(data)
    assert not form.is_valid()
    assert "final_surface" in form.errors


def test_existing_surface_can_be_zero():
    data = {
        "created_surface": 50,
        "existing_surface": 0,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    data.update(compute_surfaces(data))

    form = MoulinetteFormAmenagement(data)
    assert form.is_valid()

    data = form.cleaned_data
    assert "final_surface" in data
    assert data["final_surface"] == 50


def test_existing_surface_cannot_be_negative():
    data = {
        "created_surface": 50,
        "final_surface": 40,
        "address": "Rue bidon",
        "lng": 1.234567,
        "lat": 1.234567,
    }
    data.update(compute_surfaces(data))

    form = MoulinetteFormAmenagement(data)
    assert not form.is_valid()
    assert "existing_surface" in form.errors

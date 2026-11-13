from envergo.security.inventory import Ecosystem, read_components


def test_inventory_lists_locked_npm_packages():
    """npm packages include development ones, named without their install path."""
    npm_components = [
        component
        for component in read_components()
        if component.ecosystem == Ecosystem.NPM
    ]
    names = {component.name for component in npm_components}
    development_package = "sass"

    assert development_package in names
    assert not any("node_modules" in name for name in names)
    assert all(component.version for component in npm_components)

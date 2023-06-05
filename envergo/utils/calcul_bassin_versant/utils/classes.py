from typing import List


class Parameters:
    def __init__(
        self,
        cartoPrecision: int,
        innerRadius: int,
        radii: List[int],
        quadrantsNb: int,
        slope: float,
    ):
        self.cartoPrecision = cartoPrecision
        self.innerRadius = innerRadius
        self.radii = radii
        self.quadrantsNb = quadrantsNb
        self.slope = slope

    def __str__(self):
        stringResult = "Parameters("
        stringResult += f"cartoPrecision: {self.cartoPrecision}"
        stringResult += f" - innerRadius: {self.innerRadius}"
        stringResult += f" - radii: {self.radii}"
        stringResult += f" - slope: {self.slope})"
        return stringResult

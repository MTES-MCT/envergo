import numpy as np


def get_carto_info(file_name):
    info = {}
    with open(file_name) as f:
        info["file_name"] = file_name
        info["ncols"] = int(f.readline().split(" ")[-1])
        info["nrows"] = int(f.readline().split(" ")[-1])
        info["xllcorner"] = float(f.readline().split(" ")[-1])
        info["yllcorner"] = float(f.readline().split(" ")[-1])
        info["cellsize"] = float(f.readline().split(" ")[-1])
        info["nodata_value"] = float(f.readline().split(" ")[-1])
        info["x_range"] = (
            round(info["xllcorner"] + info["cellsize"] / 2),
            round(
                info["xllcorner"]
                + info["ncols"] * info["cellsize"]
                - info["cellsize"] / 2
            ),
        )
        info["y_range"] = (
            round(info["yllcorner"] - info["cellsize"] / 2),
            round(
                info["yllcorner"]
                + info["nrows"] * info["cellsize"]
                - info["cellsize"] * 3 / 2
            ),
        )
    return info


def load_carto(file_name):
    info = get_carto_info(file_name)
    carto = np.loadtxt(file_name, skiprows=6)
    carto[carto == info["nodata_value"]] = np.nan
    return carto


def get_bottom_left_corner(carto_file_name):
    info = get_carto_info(carto_file_name)
    return (info["x_range"][0], info["y_range"][0])


def save_list_to_carto(data_list, file_name, info):
    # extract coordinates and altitudes separately
    coordinates = [element[0] for element in data_list]
    altitudes = [element[1] for element in data_list]

    # convert coordinates and altitudes to numpy arrays
    coordinates_array = np.array(coordinates)
    altitudes_array = np.array(altitudes)

    # create the 2d numpy array with coordinates as indices and altitudes as values
    x_coords, y_coords = coordinates_array.T
    num_x = len(np.unique(x_coords))
    num_y = len(np.unique(y_coords))
    result_array = np.zeros((num_y, num_x))
    x_indices = np.searchsorted(np.unique(x_coords), x_coords)
    y_indices = num_y - 1 - np.searchsorted(np.unique(y_coords), y_coords)
    result_array[y_indices, x_indices] = altitudes_array

    save_array_to_carto(
        np.reshape(result_array, (info["ncols"], info["nrows"])), file_name, info
    )


def save_array_to_carto(array, file_name, info):
    header = "ncols     %s\n" % info["ncols"]
    header += "nrows    %s\n" % info["nrows"]
    header += "xllcorner %s\n" % info["xllcorner"]
    header += "yllcorner %s\n" % info["yllcorner"]
    header += "cellsize %s\n" % info["cellsize"]
    header += "nodata_value %s\n" % info["nodata_value"]
    array[np.isnan(array) | (array is None)] = float(info["nodata_value"])

    np.savetxt(file_name, array, header=header, fmt="%1.2f")


def create_quadrants(carto_precision, inner_radius, radii, quadrants_nb):
    quarter_points_nb = int(np.ceil(radii[-1] / carto_precision))
    quadrants_bins = np.linspace(0, 2 * np.pi, quadrants_nb + 1)
    quadrants = [[[] for _ in range(len(radii))] for _ in range(quadrants_nb)]
    inner_alti_points = []

    points = np.mgrid[
        -quarter_points_nb : quarter_points_nb + 1,
        -quarter_points_nb : quarter_points_nb + 1,
    ]
    displacements = carto_precision * points
    new_points = displacements[0] + 1j * displacements[1]

    # find the corresponding 'donut' for each point
    distances = np.abs(new_points)
    radius_nbs = np.searchsorted(
        np.concatenate(([inner_radius], radii, [np.inf])), distances
    )

    # find the quadrant for each point
    angles = np.angle(new_points) % (2 * np.pi)
    quad_nbs = np.digitize(angles, quadrants_bins) - 1

    # process the points based on their quadrant and radius using the masks
    for quad_nb in range(quadrants_nb):
        for radius_nb in range(len(radii)):
            mask = np.logical_and(quad_nbs == quad_nb, radius_nbs == radius_nb + 1)
            quad_points = new_points[mask]
            quadrants[quad_nb][radius_nb].extend(
                zip(
                    np.round(quad_points.real).astype(int),
                    np.round(quad_points.imag).astype(int),
                )
            )
            # convert the extended points to a num_py array
            quadrants[quad_nb][radius_nb] = np.array(
                quadrants[quad_nb][radius_nb], dtype=np.int32
            )

    inner_points = np.array(new_points[radius_nbs == 0])
    inner_alti_points.extend(
        zip(
            np.round(inner_points.real).astype(int),
            np.round(inner_points.imag).astype(int),
        )
    )

    return inner_alti_points, quadrants


def update_origin(origin, points):
    return np.add(points, origin)

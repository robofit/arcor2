"""
approx_ground_truth = {
    10: Pose(
    Position(-0.07687785, -0.17799290, 1.26817000), Orientation(0.00200334, -0.02360515, -0.02136502, 0.99949100)),
    11: Pose(
    Position(0.05636619, -0.20195630, 1.21705500), Orientation(0.00862710, -0.02130816, -0.01611331, 0.99960580))
}

camera_matrix = np.array(
    [
        [478.4944, 0.00000, 314.5086],
        [0.00000, 469.6241, 246.7942],
        [0.00000, 0.00000, 1]
    ])

dist_matrix = np.array([0.90000, 0.00000, 0.05000, 0.00000, 0.00000, 1.00000, 0.00000, 0.00000])

marker_size = 0.1

frame = cv2.imread("markers.png")
"""


def test_calibration() -> None:
    pass

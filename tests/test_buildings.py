import numpy as np
import pandas as pd

from prep.buildings import grid_weights


def test_each_building_goes_to_nearest_point():
    grid = pd.DataFrame({"lat": [33.5, 33.5], "lon": [126.5, 126.51]})
    b = np.array([[33.5, 126.5001], [33.5, 126.5002], [33.5, 126.5099]])
    assert list(grid_weights(grid, b)) == [2.0, 1.0]

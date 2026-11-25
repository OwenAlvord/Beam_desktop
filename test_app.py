import unittest

from app import (
    geographic_area,
    calculate_pour,
    estimate_cost,
    check_working_time,
    format_clock_time,
    format_duration,
    format_schedule_time,
)


class CalculationTests(unittest.TestCase):
    def test_typed_40_by_60_volume_details(self):
        result = calculate_pour(
            area=2400, thickness=6, waste=5, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420,
        )
        self.assertAlmostEqual(result["unwasted_volume"], 44.4444444444, places=2)
        self.assertAlmostEqual(result["volume_with_waste"], 46.6666666667, places=2)
        self.assertAlmostEqual(result["full_unload_minutes"], 20)
        self.assertAlmostEqual(result["round_trip_minutes"], 70)
        self.assertAlmostEqual(result["pour_duration_minutes"], 94)
        arrivals = [format_clock_time(420 + index * 20) for index in range(5)]
        self.assertEqual(arrivals, ["7:00 AM", "7:20 AM", "7:40 AM", "8:00 AM", "8:20 AM"])
        truck_numbers = [(index % 4) + 1 for index in range(5)]
        self.assertEqual(truck_numbers, [1, 2, 3, 4, 1])
    def test_typed_40_by_60_example(self):
        result = calculate_pour(
            area=2400,
            thickness=6,
            waste=5,
            truck_capacity=10,
            one_way_travel=20,
            placement_rate=30,
            washout=10,
            arrival_minutes=420,
        )
        self.assertEqual(result["ordered_volume"], 47.0)
        self.assertEqual(result["truckloads"], 5)
        self.assertEqual(result["trucks_in_rotation"], 4)
        self.assertEqual(result["load_sizes"], [10, 10, 10, 10, 7])
        self.assertEqual(result["pour_duration_minutes"], 94)
        self.assertEqual(format_duration(94), "1h 34m")
        self.assertEqual(format_clock_time(420 + 94), "8:34 AM")

    def test_typed_20_by_20_example(self):
        result = calculate_pour(
            area=400,
            thickness=4,
            waste=0,
            truck_capacity=10,
            one_way_travel=20,
            placement_rate=30,
            washout=10,
            arrival_minutes=420,
        )
        self.assertEqual(result["ordered_volume"], 5.0)
        self.assertEqual(result["truckloads"], 1)
        self.assertEqual(result["trucks_in_rotation"], 1)
        self.assertEqual(result["pour_duration_minutes"], 10)
        self.assertEqual(format_clock_time(430), "7:10 AM")

    def test_short_load_fee_and_full_load_fee(self):
        short = calculate_pour(
            area=2400, thickness=6, waste=5, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420
        )
        self.assertEqual(estimate_cost(short["ordered_volume"], 150, 75, short["final_load_size"], 10), (7050, 75))
        full = dict(short)
        full["ordered_volume"] = 50
        full["final_load_size"] = 10
        self.assertEqual(estimate_cost(50, 150, 75, 10, 10), (7500, 0))

    def test_midnight_wrap(self):
        self.assertEqual(format_clock_time(23 * 60 + 50), "11:50 PM")
        self.assertEqual(format_clock_time(24 * 60 + 20), "12:20 AM")
        self.assertEqual(format_schedule_time(24 * 60 + 20), "12:20 AM (+1 day)")

    def test_geographic_polygon_area(self):
        corners = [
            (40.2500, -111.6500),
            (40.2510, -111.6500),
            (40.2510, -111.6490),
            (40.2500, -111.6490),
        ]
        area = geographic_area(corners)
        self.assertAlmostEqual(area, 101800, delta=101800 * 0.01)
        self.assertLessEqual(abs(area - 101800) / 101800, 0.01)

    def test_cost_validation_cases(self):
        short = calculate_pour(
            area=2400, thickness=6, waste=5, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420,
        )
        concrete, fee = estimate_cost(short["ordered_volume"], 150, 75,
                                      short["final_load_size"], 10)
        self.assertEqual(concrete, 7050)
        self.assertEqual(concrete + fee, 7125)

        small = calculate_pour(
            area=400, thickness=4, waste=0, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420,
        )
        concrete, fee = estimate_cost(small["ordered_volume"], 150, 75,
                                      small["final_load_size"], 10)
        self.assertEqual(concrete, 750)
        self.assertEqual(concrete + fee, 825)

        concrete, fee = estimate_cost(50, 150, 75, 10, 10)
        self.assertEqual(concrete, 7500)
        self.assertEqual(fee, 0)
        self.assertEqual(concrete + fee, 7500)

        concrete, fee = estimate_cost(47, 150, 0, 7, 10)
        self.assertEqual(concrete, 7050)
        self.assertEqual(fee, 0)

    def test_set_time_validation_cases(self):
        large = calculate_pour(
            area=2400, thickness=6, waste=5, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420,
        )
        self.assertEqual(large["pour_duration_minutes"], 94)
        self.assertEqual(check_working_time(100, large["pour_duration_minutes"]),
                         (True, 6))
        self.assertEqual(check_working_time(94, large["pour_duration_minutes"]),
                         (True, 0))
        self.assertEqual(check_working_time(90, large["pour_duration_minutes"]),
                         (False, 4))

        small = calculate_pour(
            area=400, thickness=4, waste=0, truck_capacity=10,
            one_way_travel=20, placement_rate=30, washout=10, arrival_minutes=420,
        )
        self.assertEqual(small["pour_duration_minutes"], 10)
        self.assertEqual(check_working_time(10, small["pour_duration_minutes"]),
                         (True, 0))
        self.assertEqual(check_working_time(9, small["pour_duration_minutes"]),
                         (False, 1))


if __name__ == "__main__":
    unittest.main()

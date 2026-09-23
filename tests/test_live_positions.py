import unittest

from tools.build_live_positions import robust_fit


class LivePositionFitTests(unittest.TestCase):
    def test_recovers_room_transform_and_rejects_bad_pin(self):
        source = [complex(0, 0), complex(50, 0), complex(0, 50), complex(50, 50), complex(80, 20)]
        pairs = [(p, 2 * p + complex(300, -700)) for p in source]
        pairs.append((complex(20, 70), complex(999, 999)))
        result = robust_fit(pairs)
        self.assertIsNotNone(result)
        self.assertEqual(result["anchors"], 5)
        self.assertLess(result["rms"], .01)

    def test_does_not_trust_two_points(self):
        self.assertIsNone(robust_fit([(0j, 100j), (50 + 0j, 150j)]))


if __name__ == "__main__":
    unittest.main()

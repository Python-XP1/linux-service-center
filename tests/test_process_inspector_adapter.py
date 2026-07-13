import unittest
from unittest.mock import patch

from diagnostics.process_inspector_adapter import (
    analyze_grouped_query,
    command_requires_advanced,
)


class CommandSafetyTests(unittest.TestCase):
    def test_read_only_commands_do_not_require_advanced_mode(self):
        commands = [
            "ps -fp 123",
            "pstree -sp 123",
            "sudo systemctl status demo.service",
            "sudo journalctl -u demo.service -n 80 --no-pager",
            "systemctl --user list-units --all",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertFalse(command_requires_advanced(command))

    def test_destructive_commands_require_advanced_mode(self):
        commands = [
            "kill 123",
            "sudo systemctl stop demo.service",
            "sudo systemctl disable demo.service",
            "systemctl --user stop demo.service",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertTrue(command_requires_advanced(command))


class GroupedAnalysisTests(unittest.TestCase):
    @patch("diagnostics.process_inspector_adapter.analyze_query")
    @patch("diagnostics.process_inspector_adapter.group_results")
    def test_grouped_results_receive_structured_command_items(
        self,
        group_results_mock,
        analyze_mock,
    ):
        analyze_mock.return_value = [{"process": {"pid": 123}}]
        group_results_mock.return_value = [
            {
                "group_key": "systemd-system:demo.service",
                "primary": {
                    "suggested_commands": [
                        "sudo systemctl status demo.service",
                        "sudo systemctl stop demo.service",
                    ],
                    "respawn_test_commands": [],
                    "slice_recovery_commands": [],
                },
                "process_count": 1,
                "pids": [123],
                "processes": [{"pid": 123}],
            }
        ]

        groups = analyze_grouped_query("demo")
        items = groups[0]["primary"]["command_items"]

        self.assertEqual(len(items), 2)
        self.assertFalse(items[0]["requires_advanced"])
        self.assertTrue(items[1]["requires_advanced"])
        analyze_mock.assert_called_once_with("demo")


if __name__ == "__main__":
    unittest.main()

# Troubleshooting

## Configuration error (exit 2)

Check `WMB_` values. Timeouts must be positive, retry counts non-negative, and log level one of `CRITICAL`, `ERROR`, `WARNING`, `INFO`, or `DEBUG`.

## Runtime error (exit 1)

Confirm `adb` is installed or set `WMB_ADB_EXECUTABLE`. Run `adb devices -l`; exactly one device must be online for automatic selection. Accept the authorization prompt on the device and reconnect offline devices.

## Interrupted (exit 130)

This indicates an intentional Ctrl+C shutdown. The runtime completes its shutdown path before exiting.

## Screenshot or display failures

Verify `adb shell wm size`, `adb shell wm density`, and `adb exec-out screencap -p` work for the selected device. Transport reads have bounded retries; input events are not repeated automatically.

## Level or package-resource failures

Reinstall from a clean wheel and confirm `word_madness_bot.resources.levels/levels.json` and the templates resource package are present. Packaged level data is validated when the runtime is composed.

## Vision or OCR uncertainty

The vision layer returns confidence and Unknown/failure paths. Do not lower thresholds until synthetic fixture tests and recorded device evidence justify the change.

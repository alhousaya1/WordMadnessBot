# Advertisement Handling

## Detection model

`AdvertisementDetection` records an interstitial, rewarded, or unknown type, confidence from zero to one, and zero or more normalized close-control candidates.

## Action selection

`AdvertisementPolicy` rejects low-confidence and unknown detections with `WAIT`. For accepted detections it chooses the strongest top-right close candidate; when no close control exists it uses Android Back.

## Bounded dismissal

Dismissal requires a positive maximum-attempt count and a visibility probe. Each attempt selects one typed action, converts normalized points using the current screen size, and records the result. Exhaustion returns an unsuccessful result rather than looping indefinitely.

## Recovery

`RecoveryStrategy` owns retry, backoff, timeout, cancellation, and exhaustion. Callers explicitly declare recoverable exceptions. Device input is not silently retried by the ADB adapter.

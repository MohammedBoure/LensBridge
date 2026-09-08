import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

enum BroadcastStatus {
  idle,
  discovering,
  connecting,
  streaming,
  disconnected,
  error,
}

/// Service managing the lifecycle of the Android background dual camera broadcast.
/// Includes fault-tolerant handling so that if one camera (e.g. front camera) is broken
/// or disabled, the application continues running seamlessly.
class StreamService extends ChangeNotifier {
  static const MethodChannel _methodChannel = MethodChannel('com.vision.app/stream');
  static const EventChannel _eventChannel = EventChannel('com.vision.app/events');

  BroadcastStatus _status = BroadcastStatus.idle;
  String _statusMessage = 'Idle';
  String _activeServerIp = '';
  String _cameraMode = 'both'; // 'both', 'rear', 'front'
  double _rearFps = 0.0;
  double _frontFps = 0.0;
  bool _isConcurrentSupported = false;

  bool _isRearActive = false;
  bool _isFrontActive = false;
  String _rearStatusMessage = 'Standby';
  String _frontStatusMessage = 'Standby';

  StreamSubscription? _eventSubscription;

  BroadcastStatus get status => _status;
  String get statusMessage => _statusMessage;
  String get activeServerIp => _activeServerIp;
  String get cameraMode => _cameraMode;
  double get rearFps => _rearFps;
  double get frontFps => _frontFps;
  bool get isConcurrentSupported => _isConcurrentSupported;
  bool get isStreaming => _status == BroadcastStatus.streaming;
  bool get isBroadcasting =>
      _status == BroadcastStatus.streaming ||
      _status == BroadcastStatus.connecting ||
      _status == BroadcastStatus.discovering;

  bool get isRearActive => _isRearActive;
  bool get isFrontActive => _isFrontActive;
  String get rearStatusMessage => _rearStatusMessage;
  String get frontStatusMessage => _frontStatusMessage;

  StreamService() {
    _initEventChannel();
    checkHardwareSupport();
  }

  void setCameraMode(String mode) {
    if (_cameraMode != mode) {
      _cameraMode = mode;
      notifyListeners();
    }
  }

  void _initEventChannel() {
    _eventSubscription = _eventChannel.receiveBroadcastStream().listen(
      (dynamic event) {
        if (event is Map) {
          _handleNativeEvent(event);
        }
      },
      onError: (error) {
        _status = BroadcastStatus.error;
        _statusMessage = 'Event stream error: $error';
        notifyListeners();
      },
    );
  }

  void _handleNativeEvent(Map<dynamic, dynamic> data) {
    final state = data['state'] as String? ?? '';
    switch (state) {
      case 'DISCOVERING':
        _status = BroadcastStatus.discovering;
        _statusMessage = data['status'] as String? ?? 'Discovering Desktop Server on Wi-Fi...';
        break;
      case 'CONNECTING':
        _status = BroadcastStatus.connecting;
        _activeServerIp = data['serverIp'] as String? ?? '';
        _statusMessage = 'Connecting to $_activeServerIp...';
        break;
      case 'STREAMING':
        _status = BroadcastStatus.streaming;
        _activeServerIp = data['serverIp'] as String? ?? _activeServerIp;
        _statusMessage = 'Live Broadcasting';
        break;
      case 'CAMERA_STATUS':
        _isRearActive = data['rearActive'] as bool? ?? _isRearActive;
        _rearStatusMessage = data['rearMessage'] as String? ?? _rearStatusMessage;
        _isFrontActive = data['frontActive'] as bool? ?? _isFrontActive;
        _frontStatusMessage = data['frontMessage'] as String? ?? _frontStatusMessage;
        break;
      case 'TELEMETRY':
        _rearFps = (data['rearFps'] as num?)?.toDouble() ?? _rearFps;
        _frontFps = (data['frontFps'] as num?)?.toDouble() ?? _frontFps;
        break;
      case 'DISCONNECTED':
        _status = BroadcastStatus.disconnected;
        _statusMessage = data['reason'] as String? ?? 'Disconnected. Retrying...';
        _rearFps = 0.0;
        _frontFps = 0.0;
        _isRearActive = false;
        _isFrontActive = false;
        break;
      case 'STOPPED':
        _status = BroadcastStatus.idle;
        _statusMessage = 'Broadcast stopped';
        _rearFps = 0.0;
        _frontFps = 0.0;
        _isRearActive = false;
        _isFrontActive = false;
        _rearStatusMessage = 'Standby';
        _frontStatusMessage = 'Standby';
        break;
      default:
        break;
    }
    notifyListeners();
  }

  Future<void> checkHardwareSupport() async {
    try {
      final supported = await _methodChannel.invokeMethod<bool>('checkConcurrentSupport');
      _isConcurrentSupported = supported ?? false;
      notifyListeners();
    } catch (_) {}
  }

  Future<void> requestPermissions() async {
    try {
      await _methodChannel.invokeMethod('requestPermissions');
    } catch (_) {}
  }

  Future<bool> startBroadcast({
    String? serverIp,
    int serverPort = 8000,
    bool autoDiscover = true,
    String? cameraMode,
  }) async {
    try {
      final mode = cameraMode ?? _cameraMode;
      _cameraMode = mode;

      await requestPermissions();
      _status = autoDiscover ? BroadcastStatus.discovering : BroadcastStatus.connecting;
      _statusMessage = autoDiscover ? 'Scanning Wi-Fi for Desktop...' : 'Connecting to $serverIp...';
      notifyListeners();

      final res = await _methodChannel.invokeMethod<bool>('startBroadcast', {
        'serverIp': serverIp ?? '',
        'serverPort': serverPort,
        'autoDiscover': autoDiscover,
        'cameraMode': mode,
      });
      return res ?? false;
    } catch (e) {
      _status = BroadcastStatus.error;
      _statusMessage = 'Failed to start service: $e';
      notifyListeners();
      return false;
    }
  }

  Future<bool> stopBroadcast() async {
    try {
      final res = await _methodChannel.invokeMethod<bool>('stopBroadcast');
      _status = BroadcastStatus.idle;
      _statusMessage = 'Idle';
      _rearFps = 0.0;
      _frontFps = 0.0;
      _isRearActive = false;
      _isFrontActive = false;
      notifyListeners();
      return res ?? false;
    } catch (e) {
      return false;
    }
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    super.dispose();
  }
}

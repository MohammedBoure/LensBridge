import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/main.dart';

void main() {
  testWidgets('VisionCamApp smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const VisionCamApp());
    expect(find.text('VISION CAM'), findsOneWidget);
  });
}

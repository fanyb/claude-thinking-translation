import Foundation
import Translation

let source = Locale.Language(identifier: "en-US")
let target = Locale.Language(identifier: "zh-Hans")
guard await LanguageAvailability().status(from: source, to: target) == .installed else {
    exit(3)
}
var session = TranslationSession(installedSource: source, target: target)
while let line = readLine() {
    do {
        let text = try JSONDecoder().decode(String.self, from: Data(line.utf8))
        var translated: String? = nil
        for _ in 0..<2 {
            do {
                let response = try await session.translate(text)
                if response.targetText.unicodeScalars.contains(where: { (0x3400...0x9fff).contains($0.value) }) {
                    translated = response.targetText
                    break
                }
            } catch {}
            // System translation sessions can stop translating while the process remains alive.
            session = TranslationSession(installedSource: source, target: target)
        }
        guard let translated else { exit(4) }
        let encoded = try JSONEncoder().encode(translated)
        FileHandle.standardOutput.write(encoded + Data([10]))
    } catch {
        FileHandle.standardOutput.write(Data("null\n".utf8))
    }
}

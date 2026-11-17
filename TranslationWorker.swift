import Foundation
import Translation

let source = Locale.Language(identifier: "en-US")
let target = Locale.Language(identifier: "zh-Hans")
guard await LanguageAvailability().status(from: source, to: target) == .installed else {
    exit(3)
}
let session = TranslationSession(installedSource: source, target: target)
while let line = readLine() {
    do {
        let text = try JSONDecoder().decode(String.self, from: Data(line.utf8))
        let response = try await session.translate(text)
        let encoded = try JSONEncoder().encode(response.targetText)
        FileHandle.standardOutput.write(encoded + Data([10]))
    } catch {
        FileHandle.standardOutput.write(Data("null\n".utf8))
    }
}

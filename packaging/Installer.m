#import <AppKit/AppKit.h>

@interface Installer : NSObject <NSApplicationDelegate>
@property NSWindow *window;
@end

@implementation Installer
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [NSApp activateIgnoringOtherApps:YES];
    NSAlert *prompt = [NSAlert new];
    prompt.messageText = @"安装 Claude 思考翻译";
    prompt.informativeText = @"安装到当前用户的应用程序文件夹，完成后打开控制面板。";
    [prompt addButtonWithTitle:@"安装"];
    [prompt addButtonWithTitle:@"取消"];
    if ([prompt runModal] != NSAlertFirstButtonReturn) {
        [NSApp terminate:nil];
        return;
    }

    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 380, 104)
        styleMask:NSWindowStyleMaskTitled backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"Claude 思考翻译";
    NSTextField *label = [NSTextField labelWithString:@"正在安装并检查 macOS 离线翻译…"];
    label.frame = NSMakeRect(22, 57, 336, 22);
    NSProgressIndicator *progress = [[NSProgressIndicator alloc] initWithFrame:NSMakeRect(22, 30, 336, 14)];
    progress.indeterminate = YES;
    [self.window.contentView addSubview:label];
    [self.window.contentView addSubview:progress];
    [progress startAnimation:nil];
    [self.window center];
    [self.window makeKeyAndOrderFront:nil];

    NSURL *payload = [NSBundle.mainBundle.resourceURL URLByAppendingPathComponent:@"Payload/install.command"];
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSTask *task = [NSTask new];
        NSPipe *pipe = [NSPipe pipe];
        task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
        task.arguments = @[payload.path];
        task.standardOutput = pipe;
        task.standardError = pipe;
        NSError *error = nil;
        BOOL started = [task launchAndReturnError:&error];
        NSData *output = started ? [pipe.fileHandleForReading readDataToEndOfFile] : nil;
        if (started) [task waitUntilExit];
        BOOL ok = started && task.terminationStatus == 0;
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.window orderOut:nil];
            NSURL *app = [NSURL fileURLWithPath:[NSHomeDirectory() stringByAppendingPathComponent:@"Applications/Claude 思考翻译.app"]];
            if (ok && [NSWorkspace.sharedWorkspace openURL:app]) {
                [NSApp terminate:nil];
                return;
            }
            NSAlert *result = [NSAlert new];
            result.messageText = ok ? @"已安装 Claude 思考翻译" : @"安装未完成";
            result.informativeText = ok ? @"请从 Finder 的用户应用程序文件夹打开 Claude 思考翻译。" :
                (error.localizedDescription ?: [[NSString alloc] initWithData:output encoding:NSUTF8StringEncoding] ?: @"请重新打开安装器。" );
            [result runModal];
            [NSApp terminate:nil];
        });
    });
}
@end

int main(void) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        app.activationPolicy = NSApplicationActivationPolicyRegular;
        Installer *installer = [Installer new];
        app.delegate = installer;
        [app run];
    }
    return 0;
}

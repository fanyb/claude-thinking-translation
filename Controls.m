#import <AppKit/AppKit.h>

@interface Controls : NSObject <NSApplicationDelegate>
@property NSWindow *window;
@property NSTextField *status;
@property NSTextField *notice;
@property NSButton *on;
@property NSButton *off;
@property NSButton *direct;
@property NSTextField *cliStatus;
@property NSButton *cliOn;
@property NSButton *cliOff;
@property NSButton *cliDirect;
@end

@implementation Controls

- (NSURL *)runtime {
    NSURL *support = [NSFileManager.defaultManager URLsForDirectory:NSApplicationSupportDirectory
                                                         inDomains:NSUserDomainMask].firstObject;
    return [support URLByAppendingPathComponent:@"Claude Offline Translation" isDirectory:YES];
}

- (NSString *)run:(NSString *)action ok:(BOOL *)ok {
    NSURL *runtime = [self runtime];
    NSURL *python = [runtime URLByAppendingPathComponent:@"venv/bin/python3"];
    if (![NSFileManager.defaultManager isExecutableFileAtPath:python.path]) {
        python = [NSURL fileURLWithPath:@"/usr/bin/python3"];
    }
    NSTask *task = [NSTask new];
    NSPipe *output = [NSPipe pipe];
    if ([action isEqualToString:@"uninstall"]) {
        task.executableURL = [NSURL fileURLWithPath:@"/bin/bash"];
        task.arguments = @[[runtime URLByAppendingPathComponent:@"install.command"].path, @"--uninstall"];
    } else {
        task.executableURL = python;
        task.arguments = @[[runtime URLByAppendingPathComponent:@"gateway.py"].path, action];
    }
    task.standardOutput = output;
    task.standardError = output;
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) {
        *ok = NO;
        return error.localizedDescription;
    }
    NSData *data = [output.fileHandleForReading readDataToEndOfFile];
    [task waitUntilExit];
    *ok = task.terminationStatus == 0;
    NSString *message = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    return [message stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
}

- (void)uninstall:(id)sender {
    NSAlert *confirm = [NSAlert new];
    confirm.messageText = @"卸载 Claude 思考翻译？";
    confirm.informativeText = @"请先恢复直连并退出使用翻译的 Claude 和 CLI 会话。卸载会删除本机翻译缓存。";
    [confirm addButtonWithTitle:@"取消"];
    [confirm addButtonWithTitle:@"卸载"];
    if ([confirm runModal] != NSAlertSecondButtonReturn) return;
    BOOL ok;
    NSString *result = [self run:@"uninstall" ok:&ok];
    if (ok) [NSApp terminate:nil];
    self.notice.stringValue = result.length ? result : @"卸载未完成。";
    self.notice.textColor = NSColor.systemRedColor;
}

- (void)refresh {
    BOOL ok;
    NSString *state = [self run:@"status" ok:&ok];
    self.status.stringValue = ok ? state : @"网关配置无法读取";
    self.status.textColor = [state isEqualToString:@"离线翻译已开启"]
        ? NSColor.systemGreenColor : NSColor.labelColor;
    self.on.enabled = ok && ![state isEqualToString:@"离线翻译已开启"];
    self.off.enabled = ok && [state isEqualToString:@"离线翻译已开启"];
    self.direct.enabled = ok && ![state isEqualToString:@"直连 CC Switch"];
    if (!ok) self.notice.stringValue = state ?: @"无法读取当前配置。";

    NSString *cliState = [self run:@"cli-status" ok:&ok];
    self.cliStatus.stringValue = ok ? cliState : @"CLI 状态无法读取";
    self.cliStatus.textColor = [cliState isEqualToString:@"离线翻译已开启"]
        ? NSColor.systemGreenColor : NSColor.labelColor;
    self.cliOn.enabled = ok && ![cliState isEqualToString:@"离线翻译已开启"];
    self.cliOff.enabled = ok && [cliState isEqualToString:@"离线翻译已开启"];
    self.cliDirect.enabled = ok && ![cliState isEqualToString:@"直连当前供应商"];
}

- (void)switchMode:(NSButton *)button {
    BOOL ok;
    NSString *result = [self run:button.identifier ok:&ok];
    [self refresh];
    self.notice.stringValue = result.length ? result : @"操作未完成。";
    self.notice.textColor = ok ? NSColor.secondaryLabelColor : NSColor.systemRedColor;
}

- (NSTextField *)label:(NSString *)value size:(CGFloat)size weight:(NSFontWeight)weight {
    NSTextField *field = [NSTextField wrappingLabelWithString:value];
    field.font = [NSFont systemFontOfSize:size weight:weight];
    field.maximumNumberOfLines = 3;
    return field;
}

- (NSButton *)button:(NSString *)title action:(NSString *)action {
    NSButton *button = [NSButton buttonWithTitle:title target:self action:@selector(switchMode:)];
    button.identifier = action;
    return button;
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    self.window = [[NSWindow alloc] initWithContentRect:NSMakeRect(0, 0, 542, 390)
        styleMask:NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
        backing:NSBackingStoreBuffered defer:NO];
    self.window.title = @"Claude 思考翻译";
    [self.window center];

    NSTextField *title = [self label:@"Claude 思考翻译" size:24 weight:NSFontWeightSemibold];
    NSTextField *detail = [self label:@"macOS 离线英译简中" size:13 weight:NSFontWeightRegular];
    detail.textColor = NSColor.secondaryLabelColor;
    NSTextField *desktopTitle = [self label:@"Claude Desktop · DeepSeek V4.1 Flash" size:14 weight:NSFontWeightMedium];
    self.status = [self label:@"正在读取状态…" size:16 weight:NSFontWeightSemibold];
    self.on = [self button:@"开启翻译" action:@"on"];
    self.off = [self button:@"恢复英文" action:@"off"];
    self.direct = [self button:@"恢复直连" action:@"direct"];
    self.notice = [self label:@"继续用过翻译的会话时，点「恢复英文」可保留工具回传。" size:12 weight:NSFontWeightRegular];
    self.notice.textColor = NSColor.secondaryLabelColor;
    NSTextField *help = [self label:@"终端运行 ~/.local/bin/claude-zh。切换 CC Switch 供应商后重开该命令。" size:12 weight:NSFontWeightRegular];
    help.textColor = NSColor.secondaryLabelColor;

    NSTextField *cliTitle = [self label:@"Claude Code CLI" size:14 weight:NSFontWeightMedium];
    self.cliStatus = [self label:@"正在读取状态…" size:16 weight:NSFontWeightSemibold];
    self.cliOn = [self button:@"CLI 开启翻译" action:@"cli-on"];
    self.cliOff = [self button:@"CLI 恢复英文" action:@"cli-off"];
    self.cliDirect = [self button:@"CLI 恢复直连" action:@"cli-direct"];
    NSStackView *cliButtons = [NSStackView stackViewWithViews:@[self.cliOn, self.cliOff, self.cliDirect]];
    cliButtons.spacing = 10;
    NSStackView *buttons = [NSStackView stackViewWithViews:@[self.on, self.off, self.direct]];
    buttons.spacing = 10;
    NSStackView *stack = [NSStackView stackViewWithViews:@[title, detail, desktopTitle, self.status, buttons,
                                                          cliTitle, self.cliStatus, cliButtons, help, self.notice]];
    stack.orientation = NSUserInterfaceLayoutOrientationVertical;
    stack.alignment = NSLayoutAttributeLeading;
    stack.spacing = 10;
    [stack setCustomSpacing:15 afterView:detail];
    [stack setCustomSpacing:20 afterView:buttons];
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    NSView *content = self.window.contentView;
    [content addSubview:stack];
    [NSLayoutConstraint activateConstraints:@[
        [stack.leadingAnchor constraintEqualToAnchor:content.leadingAnchor constant:25],
        [stack.trailingAnchor constraintEqualToAnchor:content.trailingAnchor constant:-25],
        [stack.topAnchor constraintEqualToAnchor:content.topAnchor constant:22],
        [help.widthAnchor constraintLessThanOrEqualToAnchor:stack.widthAnchor],
        [self.notice.widthAnchor constraintLessThanOrEqualToAnchor:stack.widthAnchor],
    ]];

    NSMenu *menu = [NSMenu new];
    NSMenuItem *item = [NSMenuItem new];
    [menu addItem:item];
    item.submenu = [NSMenu new];
    if ([NSFileManager.defaultManager isExecutableFileAtPath:[[self runtime] URLByAppendingPathComponent:@"install.command"].path]) {
        NSMenuItem *uninstall = [item.submenu addItemWithTitle:@"卸载 Claude 思考翻译…" action:@selector(uninstall:) keyEquivalent:@""];
        uninstall.target = self;
    }
    [item.submenu addItemWithTitle:@"退出 Claude 思考翻译" action:@selector(terminate:) keyEquivalent:@"q"];
    NSApp.mainMenu = menu;
    [self refresh];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
}

- (void)applicationDidBecomeActive:(NSNotification *)notification {
    if (self.window) [self refresh];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)app {
    return YES;
}
@end

int main(void) {
    @autoreleasepool {
        NSApplication *app = NSApplication.sharedApplication;
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        Controls *controls = [Controls new];
        app.delegate = controls;
        [app run];
    }
    return 0;
}

// Print an HTML file to a paginated A4 PDF with the system WebKit (no Chrome needed).
// Build: swiftc -O -o tools/html_to_pdf tools/html_to_pdf.swift
// Run:   tools/html_to_pdf output/paper/resident.html output/paper/resident.pdf
import Cocoa
import WebKit

let args = CommandLine.arguments
guard args.count == 3 else { fputs("usage: html_to_pdf in.html out.pdf\n", stderr); exit(2) }
let inURL = URL(fileURLWithPath: args[1]).standardizedFileURL
let outURL = URL(fileURLWithPath: args[2]).standardizedFileURL

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)

// A4 in points, 13 mm / 15 mm margins as in the page's @page rule.
let paper = NSSize(width: 595.28, height: 841.89)
let mTop: CGFloat = 36.85, mSide: CGFloat = 42.52
let printable = NSSize(width: paper.width - 2*mSide, height: paper.height - 2*mTop)

let window = NSWindow(contentRect: NSRect(origin: .zero, size: printable), styleMask: [.borderless], backing: .buffered, defer: false)
let config = WKWebViewConfiguration()
let webView = WKWebView(frame: NSRect(origin: .zero, size: printable), configuration: config)
window.contentView = webView

final class Delegate: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        // give images and fonts a moment
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { printIt(webView) }
    }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { fail(error) }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { fail(error) }
    func fail(_ e: Error) { fputs("load failed: \(e)\n", stderr); exit(1) }
}
let delegate = Delegate()
webView.navigationDelegate = delegate

func printIt(_ wv: WKWebView) {
    let pi = NSPrintInfo(dictionary: [:])
    pi.paperSize = paper
    pi.topMargin = mTop; pi.bottomMargin = mTop; pi.leftMargin = mSide; pi.rightMargin = mSide
    pi.horizontalPagination = .fit
    pi.verticalPagination = .automatic
    pi.isHorizontallyCentered = false
    pi.isVerticallyCentered = false
    pi.jobDisposition = .save
    pi.dictionary()[NSPrintInfo.AttributeKey.jobSavingURL] = outURL
    let op = wv.printOperation(with: pi)
    op.showsPrintPanel = false
    op.showsProgressPanel = false
    op.view?.frame = NSRect(origin: .zero, size: printable)
    op.runModal(for: window, delegate: printDone, didRun: #selector(PrintDone.printOperationDidRun(_:success:contextInfo:)), contextInfo: nil)
}

final class PrintDone: NSObject {
    @objc func printOperationDidRun(_ op: NSPrintOperation, success: Bool, contextInfo: UnsafeMutableRawPointer?) {
        // the save job may still be flushing; wait until the file ends with %%EOF
        var tries = 0
        func poll() {
            if let d = try? Data(contentsOf: outURL), d.count > 1000,
               String(decoding: d.suffix(32), as: UTF8.self).contains("%%EOF") {
                print("wrote \(outURL.path) (\(d.count) bytes, success=\(success))"); exit(0)
            }
            tries += 1
            if tries > 600 { fputs("timed out waiting for PDF (success=\(success))\n", stderr); exit(1) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1, execute: poll)
        }
        poll()
    }
}
let printDone = PrintDone()

try? FileManager.default.removeItem(at: outURL)
webView.loadFileURL(inURL, allowingReadAccessTo: inURL.deletingLastPathComponent())
app.run()

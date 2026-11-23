// Add the running title and "page / total" to the foot of every page of a PDF (for the WebKit fallback, which prints no footer).
// Run: swift tools/pdf_footer.swift in.pdf out.pdf "The Capital Census · Holding the World in One’s Own Hours · v1.0"
import Cocoa
import PDFKit

let a = CommandLine.arguments
guard a.count == 4, let doc = PDFDocument(url: URL(fileURLWithPath: a[1])), doc.pageCount > 0 else {
    fputs("usage: pdf_footer in.pdf out.pdf title\n", stderr); exit(2)
}
let title = a[3], n = doc.pageCount
let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.systemFont(ofSize: 7), .foregroundColor: NSColor(white: 0.47, alpha: 1)]
let side: CGFloat = 42.52, base: CGFloat = 16      // 15 mm side margin, footer baseline 16 pt above the page foot

var mb = doc.page(at: 0)!.bounds(for: .mediaBox)
guard let ctx = CGContext(URL(fileURLWithPath: a[2]) as CFURL, mediaBox: &mb, nil) else { fputs("cannot write \(a[2])\n", stderr); exit(1) }
for i in 0..<n {
    let pg = doc.page(at: i)!
    var r = pg.bounds(for: .mediaBox)
    ctx.beginPage(mediaBox: &r)
    pg.draw(with: .mediaBox, to: ctx)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(cgContext: ctx, flipped: false)
    NSAttributedString(string: title, attributes: attrs).draw(at: NSPoint(x: r.minX + side, y: r.minY + base))
    let rs = NSAttributedString(string: "\(i + 1) / \(n)", attributes: attrs)
    rs.draw(at: NSPoint(x: r.maxX - side - rs.size().width, y: r.minY + base))
    NSGraphicsContext.restoreGraphicsState()
    ctx.endPage()
}
ctx.closePDF()
print("wrote \(a[2]) (\(n) pages)")

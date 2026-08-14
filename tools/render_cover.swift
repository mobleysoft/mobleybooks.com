#!/usr/bin/env swift
import AppKit
import Foundation

guard CommandLine.arguments.count == 7 else {
    FileHandle.standardError.write(Data("usage: render_cover.swift ART OUTPUT TITLE SUBTITLE AUTHOR ACCENT_HEX\n".utf8))
    exit(2)
}

let artPath = CommandLine.arguments[1]
let outputPath = CommandLine.arguments[2]
let title = CommandLine.arguments[3]
let subtitle = CommandLine.arguments[4]
let author = CommandLine.arguments[5]
let accentHex = CommandLine.arguments[6].trimmingCharacters(in: CharacterSet(charactersIn: "#"))

func color(_ hex: String) -> NSColor {
    var value: UInt64 = 0
    Scanner(string: hex).scanHexInt64(&value)
    return NSColor(
        red: CGFloat((value >> 16) & 0xff) / 255,
        green: CGFloat((value >> 8) & 0xff) / 255,
        blue: CGFloat(value & 0xff) / 255,
        alpha: 1
    )
}

guard let source = NSImage(contentsOfFile: artPath) else {
    FileHandle.standardError.write(Data("cannot read art: \(artPath)\n".utf8))
    exit(1)
}

let width = 1600
let height = 2560
guard let bitmap = NSBitmapImageRep(
    bitmapDataPlanes: nil,
    pixelsWide: width,
    pixelsHigh: height,
    bitsPerSample: 8,
    samplesPerPixel: 4,
    hasAlpha: true,
    isPlanar: false,
    colorSpaceName: .deviceRGB,
    bytesPerRow: 0,
    bitsPerPixel: 0
) else { exit(1) }

let context = NSGraphicsContext(bitmapImageRep: bitmap)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context

let canvas = NSRect(x: 0, y: 0, width: width, height: height)
NSColor.black.setFill()
canvas.fill()

let sourceRatio = source.size.width / source.size.height
let canvasRatio = CGFloat(width) / CGFloat(height)
var drawRect = canvas
if sourceRatio > canvasRatio {
    let drawWidth = CGFloat(height) * sourceRatio
    drawRect.origin.x = (CGFloat(width) - drawWidth) / 2
    drawRect.size.width = drawWidth
} else {
    let drawHeight = CGFloat(width) / sourceRatio
    drawRect.origin.y = (CGFloat(height) - drawHeight) / 2
    drawRect.size.height = drawHeight
}
source.draw(in: drawRect, from: .zero, operation: .sourceOver, fraction: 1)

let topGradient = NSGradient(colors: [NSColor.black.withAlphaComponent(0.92), NSColor.black.withAlphaComponent(0.0)])!
topGradient.draw(in: NSRect(x: 0, y: 1420, width: width, height: 1140), angle: 90)
let bottomGradient = NSGradient(colors: [NSColor.black.withAlphaComponent(0.94), NSColor.black.withAlphaComponent(0.0)])!
bottomGradient.draw(in: NSRect(x: 0, y: 0, width: width, height: 780), angle: -90)

let accent = color(accentHex)
accent.withAlphaComponent(0.78).setStroke()
let border = NSBezierPath(rect: NSRect(x: 54, y: 54, width: 1492, height: 2452))
border.lineWidth = 2
border.stroke()

func font(_ name: String, _ size: CGFloat, fallback: NSFont) -> NSFont {
    return NSFont(name: name, size: size) ?? fallback
}

let imprintStyle = NSMutableParagraphStyle()
imprintStyle.alignment = .left
let imprintAttributes: [NSAttributedString.Key: Any] = [
    .font: font("Avenir Next Condensed Demi Bold", 26, fallback: .boldSystemFont(ofSize: 26)),
    .foregroundColor: accent,
    .kern: 7.0,
    .paragraphStyle: imprintStyle,
]
"MOBLEYBOOKS ORIGINAL".draw(in: NSRect(x: 118, y: 2370, width: 1000, height: 60), withAttributes: imprintAttributes)

let titleAttributes: [NSAttributedString.Key: Any] = [
    .font: font("Bodoni 72", title.count > 18 ? 156 : 196, fallback: .systemFont(ofSize: 180, weight: .medium)),
    .foregroundColor: NSColor(calibratedWhite: 0.98, alpha: 1),
    .kern: -5.0,
]
title.draw(
    with: NSRect(x: 112, y: 1770, width: 1376, height: 520),
    options: [.usesLineFragmentOrigin, .usesFontLeading],
    attributes: titleAttributes
)

let subtitleAttributes: [NSAttributedString.Key: Any] = [
    .font: font("Avenir Next Condensed Demi Bold", 40, fallback: .boldSystemFont(ofSize: 40)),
    .foregroundColor: accent,
    .kern: 6.0,
]
subtitle.uppercased().draw(
    with: NSRect(x: 120, y: 1650, width: 1250, height: 100),
    options: [.usesLineFragmentOrigin],
    attributes: subtitleAttributes
)

accent.setFill()
NSRect(x: 120, y: 294, width: 190, height: 8).fill()
let authorAttributes: [NSAttributedString.Key: Any] = [
    .font: font("Avenir Next Condensed Demi Bold", 57, fallback: .boldSystemFont(ofSize: 57)),
    .foregroundColor: NSColor.white,
    .kern: 5.5,
]
author.uppercased().draw(in: NSRect(x: 118, y: 190, width: 1360, height: 80), withAttributes: authorAttributes)
let editionAttributes: [NSAttributedString.Key: Any] = [
    .font: font("Avenir Next Condensed Demi Bold", 24, fallback: .boldSystemFont(ofSize: 24)),
    .foregroundColor: NSColor.white.withAlphaComponent(0.7),
    .kern: 6.0,
]
"DIGITAL FIRST EDITION".draw(in: NSRect(x: 120, y: 126, width: 900, height: 44), withAttributes: editionAttributes)

context.flushGraphics()
NSGraphicsContext.restoreGraphicsState()

guard let data = bitmap.representation(using: .png, properties: [:]) else { exit(1) }
try data.write(to: URL(fileURLWithPath: outputPath), options: .atomic)

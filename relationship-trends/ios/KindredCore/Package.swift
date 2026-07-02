// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "KindredCore",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "KindredCore", targets: ["KindredCore"]),
    ],
    targets: [
        .target(name: "KindredCore"),
        .testTarget(name: "KindredCoreTests", dependencies: ["KindredCore"]),
    ]
)

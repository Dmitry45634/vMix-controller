[app]

title = vMix Controller Mobile
package.name = vmixcontroller
package.domain = org.dmitry

source.dir = .
source.include_exts = py,png,jpg,kv,atlas

version = 0.1

requirements = python3,kivy,requests

orientation = portrait

[buildozer]

log_level = 2
warn_on_root = 1

[app:permissions]
android.permissions = INTERNET,ACCESS_NETWORK_STATE

[app:buildozer]
android.api = 31
android.minapi = 21

# Maintainer: Anton Semjonov <hello \ät semjonov.de>
# Note: this PKGBUILD is meant to be built from a git checkout

_pkgname="sbkernelsign"
pkgname="$_pkgname-git"
pkgdesc="Create signed kernel images bundled with initrd and efistub for secureoot."

pkgver=r42.9797299
pkgrel=1

arch=('any')
url="https://github.com/ansemjo/$_pkgname"
license=('MIT')

depends=('systemd' 'binutils' 'sbsigntools' 'python')
makedepends=('git')

provides=($_pkgname)
conflicts=($_pkgname)
backup=("etc/$_pkgname.cfg")
source=("pkgbuild::git+file:///$PWD")
sha256sums=("SKIP")

pkgver() {
  # no tags yet, use number of revisions
  printf "r%s.%s" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

package() {
  cd "$srcdir/pkgbuild"
  install -D -m755 -t "$pkgdir/usr/bin/" "$_pkgname"
  ln -sT "$_pkgname"  "$pkgdir/usr/bin/efistub-combine"
  install -D -m644 -t "$pkgdir/etc/" "$_pkgname.cfg"
  install -D -m644 -t "$pkgdir/usr/share/libalpm/hooks/" "aux/96-$_pkgname.hook"        
  install -D -m644 -t "$pkgdir/usr/share/libalpm/hooks/" "aux/50-$_pkgname-remove.hook"
  install -D -m644 -t "$pkgdir/usr/share/licenses/$_pkgname/" "LICENSE"
}

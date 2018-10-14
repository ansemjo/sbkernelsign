DESTDIR :=
BIN     := /usr/bin
ETC     := /etc
HOOKS   := /usr/share/libalpm/hooks
INSTALL := \
	$(DESTDIR)$(BIN)/sbkernelsign \
	$(DESTDIR)$(BIN)/efistub-combine \
	$(DESTDIR)$(ETC)/sbkernelsign.cfg
INSTALL_HOOK := \
	$(DESTDIR)$(HOOKS)/96-sbkernelsign.hook

.PHONY: install
install : $(INSTALL)

.PHONY: install-hook
install-hook : $(INSTALL_HOOK)

.PHONY: all
all : install install-hook

$(DESTDIR)$(BIN)/% : %
	install -D -m 755 -t $(@D) $<

$(DESTDIR)$(ETC)/% : %
	install -D -b -m 644 -t $(@D) $<

$(DESTDIR)$(HOOKS)/% : %
	install -D -m 644 -t $(@D) $<
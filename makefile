DESTDIR :=
BIN     := /usr/bin
ETC     := /etc
INSTALL := \
	$(DESTDIR)$(BIN)/sbkernelsign \
	$(DESTDIR)$(BIN)/efistub-combine \
	$(DESTDIR)$(ETC)/sbkernelsign.cfg

.PHONY: install
install : $(INSTALL)

$(DESTDIR)$(BIN)/% : %
	install -D -m 755 -t $(@D) $<

$(DESTDIR)$(ETC)/% : %
	install -D -b -m 644 -t $(@D) $<
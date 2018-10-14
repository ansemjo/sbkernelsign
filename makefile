DESTDIR :=
INSTALL := \
	$(DESTDIR)/usr/bin/sbkernelsign \
	$(DESTDIR)/usr/bin/efistub-combine \
	$(DESTDIR)/etc/sbkernelsign.cfg

install : $(INSTALL)

$(DESTDIR)$(PREFIX)/bin/% : %
	install -D -m 755 -t $(@D) $<

$(DESTDIR)/etc/% : %
	install -D -m 644 -t $(@D) $<
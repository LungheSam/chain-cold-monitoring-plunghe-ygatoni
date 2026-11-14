// Door QR code (supervisors): print it and stick it on the fridge. Scanning it opens /unlock/<unit>.
import { QRCodeSVG } from 'qrcode.react';
import { ExternalLink, Printer, QrCode } from 'lucide-react';
import { UNIT_ID } from '../config.js';

export default function DoorQr() {
  // The link uses the address the dashboard is served from (the Firebase Hosting URL once deployed)
  const link = `${window.location.origin}/unlock/${UNIT_ID}`;
  return (
    <>
      <h1 className="no-print page-title"><QrCode size={24} />Door QR code</h1>
      <p className="no-print muted">
        Print this page and stick the label on the fridge door. A supervisor scans it with a phone, signs
        in and presses “Unlock door”. The code is only a link and holds no password: anyone can scan it,
        but only a signed-in supervisor can open the lock, and every unlock is logged.
      </p>
      {window.location.hostname === 'localhost' && (
        <p className="no-print pill warn">
          This page is open on localhost, so the code points to this laptop. Print it from the deployed
          dashboard instead.
        </p>
      )}

      <div>
        <div className="qr-label">
          <div className="qr-title">❄ Vaccine fridge {UNIT_ID}</div>
          <QRCodeSVG value={link} size={220} level="M" marginSize={2} />
          <div className="qr-text">Scan to unlock (supervisors)</div>
          <div className="qr-link">{link}</div>
          <div className="qr-text">Or use your keypad PIN, then #</div>
        </div>
      </div>

      <p className="no-print">
        <button type="button" onClick={() => window.print()}><Printer size={16} />Print label</button>{' '}
        <a className="button secondary" href={link}><ExternalLink size={16} />Try the link</a>
      </p>
    </>
  );
}

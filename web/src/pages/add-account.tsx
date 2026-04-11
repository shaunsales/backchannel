import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ServiceIcon } from "@/components/service-icon";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

const SERVICES = [
  { key: "notion", name: "Notion", desc: "Sync pages and databases" },
  { key: "telegram", name: "Telegram", desc: "Sync messages from chats" },
  { key: "gmail", name: "Gmail", desc: "Sync emails via IMAP" },
  { key: "whatsapp", name: "WhatsApp", desc: "Sync messages via bridge" },
];

interface AddAccountDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddAccountDialog({ open, onOpenChange }: AddAccountDialogProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [step, setStep] = useState(1);
  const [serviceType, setServiceType] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [resultId, setResultId] = useState("");

  // Credential fields
  const [notionToken, setNotionToken] = useState("");
  const [gmailEmail, setGmailEmail] = useState("");
  const [gmailPassword, setGmailPassword] = useState("");
  const [telegramApiId, setTelegramApiId] = useState("");
  const [telegramApiHash, setTelegramApiHash] = useState("");
  const [telegramPhone, setTelegramPhone] = useState("");

  function reset() {
    setStep(1);
    setServiceType("");
    setDisplayName("");
    setError("");
    setResultId("");
    setNotionToken("");
    setGmailEmail("");
    setGmailPassword("");
    setTelegramApiId("");
    setTelegramApiHash("");
    setTelegramPhone("");
  }

  function handleClose(v: boolean) {
    if (!v) reset();
    onOpenChange(v);
  }

  function selectService(key: string) {
    setServiceType(key);
    setDisplayName(SERVICES.find((s) => s.key === key)?.name ?? key);
    setStep(2);
    setError("");
  }

  async function handleConnect() {
    setError("");
    setConnecting(true);
    try {
      let creds: Record<string, string> = {};
      if (serviceType === "notion") {
        if (!notionToken.trim()) throw new Error("API token is required.");
        creds = { token: notionToken.trim() };
      } else if (serviceType === "gmail") {
        if (!gmailEmail.trim() || !gmailPassword.trim())
          throw new Error("Email and app password are required.");
        creds = { email: gmailEmail.trim(), app_password: gmailPassword.trim() };
      } else if (serviceType === "telegram") {
        if (!telegramApiId.trim() || !telegramApiHash.trim() || !telegramPhone.trim())
          throw new Error("API ID, API Hash, and phone number are required.");
        creds = {
          api_id: telegramApiId.trim(),
          api_hash: telegramApiHash.trim(),
          phone: telegramPhone.trim(),
        };
      } else {
        throw new Error(`${serviceType} is not yet supported.`);
      }

      const { id } = await api.createService(serviceType, displayName.trim() || serviceType);
      try {
        await api.connectService(id, creds);
        await api.testService(id);
        setResultId(id);
        setStep(3);
        qc.invalidateQueries({ queryKey: ["services"] });
        qc.invalidateQueries({ queryKey: ["dashboard"] });
      } catch (e) {
        await api.deleteService(id);
        throw e;
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setConnecting(false);
    }
  }

  const stepTitles = ["Choose a service", "Enter credentials", "Done"];

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Account</DialogTitle>
          <DialogDescription>
            {stepTitles[step - 1]}
          </DialogDescription>
        </DialogHeader>

        {/* Step indicator */}
        <div className="flex items-center gap-2 py-2">
          {[1, 2, 3].map((n, i) => (
            <div key={n} className="contents">
              {i > 0 && <div className="h-px flex-1 bg-border" />}
              <div
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                  step >= n
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {n}
              </div>
            </div>
          ))}
        </div>

        {/* Step 1: Pick service */}
        {step === 1 && (
          <div className="flex flex-col gap-1.5">
            {SERVICES.map((s) => (
              <button
                key={s.key}
                onClick={() => selectService(s.key)}
                className="flex items-center gap-3 rounded-lg border border-border/50 p-3 text-left transition-colors hover:border-primary/30 hover:bg-accent/50"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <ServiceIcon type={s.key} className="h-4 w-4 opacity-80" />
                </div>
                <div>
                  <p className="text-sm font-semibold">{s.name}</p>
                  <p className="text-[11px] text-muted-foreground">{s.desc}</p>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Step 2: Credentials */}
        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium">Display Name</label>
              <Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
            </div>

            {serviceType === "notion" && (
              <div>
                <label className="mb-1 block text-xs font-medium">API Token</label>
                <Input
                  type="password"
                  placeholder="ntn_…"
                  value={notionToken}
                  onChange={(e) => setNotionToken(e.target.value)}
                />
                <p className="mt-1 text-[10px] text-muted-foreground">
                  Create an integration at notion.so/my-integrations
                </p>
              </div>
            )}

            {serviceType === "gmail" && (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium">Email</label>
                  <Input
                    placeholder="you@gmail.com"
                    value={gmailEmail}
                    onChange={(e) => setGmailEmail(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium">App Password</label>
                  <Input
                    type="password"
                    value={gmailPassword}
                    onChange={(e) => setGmailPassword(e.target.value)}
                  />
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Generate at myaccount.google.com/apppasswords
                  </p>
                </div>
              </>
            )}

            {serviceType === "telegram" && (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium">API ID</label>
                  <Input
                    placeholder="12345678"
                    value={telegramApiId}
                    onChange={(e) => setTelegramApiId(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium">API Hash</label>
                  <Input
                    type="password"
                    value={telegramApiHash}
                    onChange={(e) => setTelegramApiHash(e.target.value)}
                  />
                  <p className="mt-1 text-[10px] text-muted-foreground">
                    Get these from my.telegram.org
                  </p>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium">Phone Number</label>
                  <Input
                    placeholder="+1234567890"
                    value={telegramPhone}
                    onChange={(e) => setTelegramPhone(e.target.value)}
                  />
                </div>
              </>
            )}

            {error && (
              <div className="rounded bg-destructive/10 border border-destructive/20 p-2">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <div className="flex justify-between pt-1">
              <Button variant="ghost" size="sm" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button size="sm" onClick={handleConnect} disabled={connecting}>
                {connecting ? (
                  <>
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" /> Connecting…
                  </>
                ) : (
                  "Connect"
                )}
              </Button>
            </div>
          </div>
        )}

        {/* Step 3: Done */}
        {step === 3 && (
          <div className="flex flex-col items-center gap-3 py-6">
            {resultId ? (
              <>
                <CheckCircle className="h-12 w-12 text-green-500" />
                <p className="text-sm font-medium">Connected successfully!</p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={() => {
                      handleClose(false);
                      navigate(`/accounts/${resultId}`);
                    }}
                  >
                    View Account
                  </Button>
                  <Button size="sm" variant="ghost" onClick={reset}>
                    Add Another
                  </Button>
                </div>
              </>
            ) : (
              <>
                <XCircle className="h-12 w-12 text-destructive" />
                <p className="text-sm font-medium">Connection failed.</p>
                <Button size="sm" variant="ghost" onClick={reset}>
                  Try Again
                </Button>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AddAccountPage() {
  return null;
}

import type React from "react";

export const SendIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.5 21.5 12 3 3.5v6.6L15 12 3 13.9z" /></svg>
);

export const ClipIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
  </svg>
);

export const TicksIcon = ({ label }: { label: string }) => (
  <svg viewBox="0 0 18 12" role="img" aria-label={label}><path d="M1 6.5l3.5 3.5L11 2.5M7.5 9.5l.5.5L17 2.5" /></svg>
);

export const MicIcon = () => (
  <svg className="mic" viewBox="0 0 24 24" role="img" aria-label="spoken">
    <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3" />
  </svg>
);

export const PhoneIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
  </svg>
);

export const AvatarIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0z" /></svg>
);

export const NewChatIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z" />
  </svg>
);

const Icon = ({ children }: { children: React.ReactNode }) => (
  <svg className="ico" viewBox="0 0 24 24" aria-hidden="true">{children}</svg>
);

export const PlaneIcon = () => (
  <Icon><path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" /></Icon>
);
export const TicketIcon = () => (
  <Icon><path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z" /><path d="M13 5v2M13 11v2M13 17v2" /></Icon>
);
export const UserIcon = () => (
  <Icon><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>
);
export const CalendarIcon = () => (
  <Icon><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></Icon>
);
export const ClockIcon = () => (
  <Icon><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></Icon>
);
export const ReasonIcon = () => (
  <Icon><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></Icon>
);
export const MailIcon = () => (
  <Icon><rect x="2" y="4" width="20" height="16" rx="2" /><path d="m22 7-10 6L2 7" /></Icon>
);
export const CardIcon = () => (
  <Icon><rect x="2" y="5" width="20" height="14" rx="2" /><path d="M2 10h20" /></Icon>
);
export const CheckCircleIcon = () => (
  <Icon><circle cx="12" cy="12" r="10" /><path d="m8.5 12 2.5 2.5 4.5-5" /></Icon>
);
export const StopCircleIcon = () => (
  <Icon><circle cx="12" cy="12" r="10" /><path d="m15 9-6 6M9 9l6 6" /></Icon>
);
export const AlertCircleIcon = () => (
  <Icon><circle cx="12" cy="12" r="10" /><path d="M12 7.5v5M12 16.5h.01" /></Icon>
);
export const ChatIcon = () => (
  <Icon><path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.8-.8L3 21l1.9-5.2a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 17 0z" /></Icon>
);

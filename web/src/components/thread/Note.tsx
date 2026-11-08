export function Note({ text }: { text: string }) {
  return (
    <div className="my-1 flex items-center gap-3 font-mono text-[10.5px] tracking-[0.16em] text-muted-foreground/80 uppercase">
      <span className="h-px flex-1 bg-gradient-to-r from-transparent to-white/12" />
      <span className="text-center">{text}</span>
      <span className="h-px flex-1 bg-gradient-to-l from-transparent to-white/12" />
    </div>
  );
}

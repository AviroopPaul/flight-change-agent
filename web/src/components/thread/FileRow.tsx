import { Paperclip } from "lucide-react";
import { useObjectUrl } from "../../hooks/useObjectUrl";
import { isImage } from "../../lib/files";

export function FileRow({ file }: { file: File }) {
  const src = useObjectUrl(isImage(file) ? file : null);
  return (
    <div className="flex flex-col gap-1.5 py-0.5">
      {src && <img src={src} alt={file.name} className="max-h-44 max-w-56 rounded-lg object-cover ring-1 ring-white/10" />}
      <span className="flex items-center gap-1.5 text-sm"><Paperclip className="size-3.5 text-muted-foreground" />{file.name}</span>
    </div>
  );
}

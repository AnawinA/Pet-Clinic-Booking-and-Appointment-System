import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError } from "../api/client";
import { endpoints } from "../api/endpoints";

const SIZE_CLASSES = {
  sm: "h-10 w-10 text-lg",
  md: "h-12 w-12 text-xl",
  lg: "h-24 w-24 text-3xl",
} as const;

type AvatarSize = keyof typeof SIZE_CLASSES;

export function PetAvatar({
  petId,
  name,
  size = "md",
  className = "",
}: {
  petId: string;
  name: string;
  size?: AvatarSize;
  className?: string;
}) {
  const photo = useQuery({
    queryKey: ["pet-photo", petId],
    queryFn: async () => {
      try {
        return await endpoints.pets.photo(petId);
      } catch (error) {
        // A missing photo is the normal placeholder state, not a user-facing error.
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled: Boolean(petId),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const [src, setSrc] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!photo.data) {
      setSrc(null);
      return;
    }
    const url = URL.createObjectURL(photo.data);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [photo.data]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  const boxClass = `${SIZE_CLASSES[size]} ${className} shrink-0 overflow-hidden rounded-2xl bg-brand-50 text-brand-700 dark:bg-brand-500/10 dark:text-brand-300`;

  return (
    <>
      {src ? (
        <button
          type="button"
          aria-label={`ดูรูปของ ${name}`}
          className={`${boxClass} block cursor-zoom-in p-0 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 dark:focus:ring-offset-slate-950`}
          onClick={() => setOpen(true)}
        >
          <img
            src={src}
            alt={`รูปของ ${name}`}
            className="h-full w-full object-cover"
            onError={() => setSrc(null)}
          />
        </button>
      ) : (
        <div className={`${boxClass} grid place-items-center`}>
          <span role="img" aria-label={`ยังไม่มีรูปของ ${name}`}>
            🐾
          </span>
        </div>
      )}

      {open && src
        ? createPortal(
            <div
              role="dialog"
              aria-modal="true"
              aria-label={`รูปของ ${name}`}
              className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 p-4 backdrop-blur-sm"
              onClick={() => setOpen(false)}
            >
              <button
                type="button"
                autoFocus
                aria-label="ปิดรูป"
                className="absolute right-4 top-4 grid h-10 w-10 place-items-center rounded-full bg-white/90 text-xl text-slate-700 shadow hover:bg-white dark:bg-slate-800/90 dark:text-slate-200 dark:hover:bg-slate-700"
                onClick={(event) => {
                  event.stopPropagation();
                  setOpen(false);
                }}
              >
                ✕
              </button>
              <img
                src={src}
                alt={`รูปของ ${name}`}
                className="max-h-[85vh] max-w-[90vw] rounded-xl object-contain shadow-2xl"
                onClick={(event) => event.stopPropagation()}
              />
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

CREATE TABLE public.content_drafts (
    id uuid PRIMARY KEY,
    title text NOT NULL,
    content text NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE TABLE public.bookings (
    id uuid PRIMARY KEY,
    customer_name text NOT NULL,
    customer_email text NOT NULL,
    service_name text NOT NULL,
    starts_at timestamptz NOT NULL,
    status text NOT NULL
);

CREATE TABLE public.users (
    id uuid PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL
);

INSERT INTO public.content_drafts (id, title, content, status, created_at) VALUES
    ('10000000-0000-4000-8000-000000000001', 'Шинэ бүтээгдэхүүний танилцуулга', 'Шинэ бүтээгдэхүүний гол онцлогийг танилцуулна.', 'draft', '2026-11-12 09:00:00+08'),
    ('10000000-0000-4000-8000-000000000002', 'Намрын урамшуулал', 'Намрын хямдралын тухай мэдээлэл.', 'draft', '2026-11-12 09:15:00+08'),
    ('10000000-0000-4000-8000-000000000003', 'Хэрэглэгчийн зөвлөгөө', 'Бүтээгдэхүүнийг зөв хэрэглэх зөвлөгөө.', 'draft', '2026-11-12 09:30:00+08');

INSERT INTO public.bookings (id, customer_name, customer_email, service_name, starts_at, status) VALUES
    ('20000000-0000-4000-8000-000000000001', 'Бат', 'bat@example.com', 'Зөвлөгөө', '2026-11-14 10:00:00+08', 'pending'),
    ('20000000-0000-4000-8000-000000000002', 'Сараа', 'saraa@example.com', 'Үзлэг', '2026-11-14 11:30:00+08', 'confirmed'),
    ('20000000-0000-4000-8000-000000000003', 'Тэмүүлэн', 'temuulen@example.com', 'Зөвлөгөө', '2026-11-15 14:00:00+08', 'pending');

INSERT INTO public.users (id, email, password_hash, created_at) VALUES
    ('30000000-0000-4000-8000-000000000001', 'Munkhbilegjin@yahoo.com', '$2b$12$SJX7I2Qqw7UtSPVGd3HeJeswv56zm5.oQzihC6sOya1mganMC3oPa', '2026-11-12 09:00:00+08');

ALTER TABLE public.content_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

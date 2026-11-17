CREATE TABLE IF NOT EXISTS public.tours (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    destination text NOT NULL,
    description text NOT NULL,
    duration_days integer NOT NULL CHECK (duration_days > 0),
    price numeric(12, 2) NOT NULL CHECK (price >= 0),
    created_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS public.staff (
    id uuid PRIMARY KEY,
    full_name text NOT NULL,
    email text NOT NULL UNIQUE,
    phone text NOT NULL,
    role text NOT NULL,
    created_at timestamptz NOT NULL
);

INSERT INTO public.tours (id, name, destination, description, duration_days, price, created_at) VALUES
    ('40000000-0000-4000-8000-000000000001', 'Хөвсгөлийн аялал', 'Хөвсгөл нуур', 'Нуурын эрэг, байгалийн үзэсгэлэнт газруудтай танилцах аялал.', 5, 1250000.00, '2026-11-12 10:00:00+08'),
    ('40000000-0000-4000-8000-000000000002', 'Говийн аялал', 'Өмнөговь', 'Элсэн манхан, хавцал болон говийн байгаль үзэх аялал.', 4, 980000.00, '2026-11-12 10:10:00+08'),
    ('40000000-0000-4000-8000-000000000003', 'Хархорины аялал', 'Өвөрхангай', 'Эртний нийслэл болон түүхэн дурсгалт газруудаар аялах аялал.', 3, 650000.00, '2026-11-12 10:20:00+08')
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.staff (id, full_name, email, phone, role, created_at) VALUES
    ('50000000-0000-4000-8000-000000000001', 'Бат-Эрдэнэ', 'bat.erdene@example.com', '+976 9911 2233', 'Аяллын хөтөч', '2026-11-12 10:00:00+08'),
    ('50000000-0000-4000-8000-000000000002', 'Сарангэрэл', 'sarangerel@example.com', '+976 9922 3344', 'Захиалгын ажилтан', '2026-11-12 10:10:00+08'),
    ('50000000-0000-4000-8000-000000000003', 'Тэмүүлэн', 'temuulen.staff@example.com', '+976 9933 4455', 'Аяллын зохицуулагч', '2026-11-12 10:20:00+08')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.tours ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.staff ENABLE ROW LEVEL SECURITY;

/**
 * Made-up customers from around the world, for tests that check a resource takes data from any locale: names, addresses,
 * postal codes and phone numbers as people there write them, in their own scripts. None of them is a real person.
 * `word` is a word of the name that a search should find, and `amount` is a balance in the local currency.
 */
export type Customer = {
  name: string
  word: string
  address: string
  city: string
  postal_code: string | null
  country: string
  phone: string
  currency: string
  amount: string
  notes: string | null
}

export const customers: Customer[] = [
  { name: '山田 花子', word: '花子', address: '神南1丁目2-3 ハイツ渋谷 405号室', city: '東京都渋谷区', postal_code: '150-0041', country: 'JP', phone: '+81 3-5412-7788', currency: 'JPY', amount: '128000', notes: 'お届けは平日の午前中' },
  { name: '王晓梅', word: '晓梅', address: '徐汇区漕溪北路88号 1203室', city: '上海市', postal_code: '200030', country: 'CN', phone: '+86 21 6487 2210', currency: 'CNY', amount: '8650.40', notes: null },
  { name: '陳大文', word: '大文', address: '九龍旺角彌敦道 610 號 18 樓 B 室', city: '香港', postal_code: null, country: 'HK', phone: '+852 2381 4466', currency: 'HKD', amount: '15420.00', notes: 'No postal codes in Hong Kong' },
  { name: '김민지', word: '민지', address: '마포구 월드컵북로 21, 3층', city: '서울특별시', postal_code: '03991', country: 'KR', phone: '+82 2-336-1452', currency: 'KRW', amount: '2450000', notes: null },
  { name: 'Анастасия Волкова', word: 'волкова', address: 'ул. Большая Никитская, д. 12, кв. 5', city: 'Москва', postal_code: '125009', country: 'RU', phone: '+7 495 621-48-37', currency: 'RUB', amount: '73500.00', notes: null },
  { name: 'Олексій Ковальчук', word: 'олексій', address: 'вул. Ярославів Вал, 22, кв. 7', city: 'Київ', postal_code: '01054', country: 'UA', phone: '+380 44 278 3301', currency: 'UAH', amount: '41200.50', notes: 'Дзвонити після 18:00' },
  { name: 'Ελένη Παπαδοπούλου', word: 'ΕΛΈΝΗ', address: 'Οδός Αιόλου 47, 3ος όροφος', city: 'Αθήνα', postal_code: '105 51', country: 'GR', phone: '+30 21 0324 9182', currency: 'EUR', amount: '980.25', notes: null },
  { name: 'ليلى حسن الشريف', word: 'ليلى', address: '٢٤ شارع قصر النيل، الدور الرابع', city: 'القاهرة', postal_code: '11511', country: 'EG', phone: '+20 2 2392 6640', currency: 'EGP', amount: '18750.00', notes: 'يفضل التواصل عبر واتساب' },
  { name: 'نوال العتيبي', word: 'العتيبي', address: 'طريق الملك فهد، حي العليا، مبنى ٧', city: 'الرياض', postal_code: '12211', country: 'SA', phone: '+966 11 465 2093', currency: 'SAR', amount: '6320.00', notes: null },
  { name: 'נועה כהן-לוי', word: 'נועה', address: 'רחוב אחד העם 31, דירה 4', city: 'תל אביב-יפו', postal_code: '6520205', country: 'IL', phone: '+972 3-566-1287', currency: 'ILS', amount: '2290.90', notes: null },
  { name: 'अनन्या शर्मा', word: 'अनन्या', address: '12, महात्मा गांधी मार्ग, लाजपत नगर', city: 'नई दिल्ली', postal_code: '110024', country: 'IN', phone: '+91 98110 46273', currency: 'INR', amount: '45999.00', notes: null },
  { name: 'สมศรี ใจดี', word: 'ใจดี', address: '99/12 ถนนสุขุมวิท แขวงคลองเตยเหนือ เขตวัฒนา', city: 'กรุงเทพมหานคร', postal_code: '10110', country: 'TH', phone: '+66 2 258 7413', currency: 'THB', amount: '12500.75', notes: null },
  { name: 'Nguyễn Thị Thu Hà', word: 'nguyễn', address: '25 Phố Hàng Bông, Phường Hàng Gai, Quận Hoàn Kiếm', city: 'Hà Nội', postal_code: '100000', country: 'VN', phone: '+84 24 3826 5147', currency: 'VND', amount: '15800000', notes: null },
  { name: 'Suharti', word: 'suharti', address: 'Jl. Malioboro No. 17', city: 'Yogyakarta', postal_code: '55271', country: 'ID', phone: '+62 274 563 218', currency: 'IDR', amount: '2750000', notes: 'One name only, as many Indonesians have' },
  { name: 'Zofia Wiśniewska-Łęcka', word: 'łęcka', address: 'ul. Świętokrzyska 14 m. 3', city: 'Warszawa', postal_code: '00-050', country: 'PL', phone: '+48 22 826 41 09', currency: 'PLN', amount: '3120.00', notes: null },
  { name: 'Jürgen Weißmüller', word: 'jürgen', address: 'Schönhauser Allee 141, Hinterhaus', city: 'Berlin', postal_code: '10437', country: 'DE', phone: '+49 30 4405 2271', currency: 'EUR', amount: '1499.99', notes: null },
  { name: 'Þórunn Guðmundsdóttir', word: 'þórunn', address: 'Laugavegur 52', city: 'Reykjavík', postal_code: '101', country: 'IS', phone: '+354 551 3842', currency: 'ISK', amount: '84500', notes: null },
  { name: 'Siobhán Ní Bhriain', word: 'siobhán', address: '14 Sráid Chill Dara', city: 'Baile Átha Cliath', postal_code: 'D02 XY45', country: 'IE', phone: '+353 1 678 2094', currency: 'EUR', amount: '310.00', notes: null },
  { name: 'Émilie Tremblay-Côté', word: 'émilie', address: '4520, rue Saint-Denis, app. 3', city: 'Montréal (Québec)', postal_code: 'H2J 2L3', country: 'CA', phone: '+1 514-555-0182', currency: 'CAD', amount: '742.10', notes: null },
  { name: 'Moana Te Rangi', word: 'moana', address: '12 Karangahape Road', city: 'Tāmaki Makaurau', postal_code: '1010', country: 'NZ', phone: '+64 9 377 0418', currency: 'NZD', amount: '199.00', notes: null },
  { name: "Chiamaka Okonkwo-Adébáyọ̀", word: 'chiamaka', address: '14 Adeola Odeku Street, Victoria Island', city: 'Lagos', postal_code: '101241', country: 'NG', phone: '+234 803 412 7765', currency: 'NGN', amount: '385000.00', notes: null },
  { name: 'João da Conceição', word: 'conceição', address: 'Rua das Flores, 123 - Apto 45', city: 'São Paulo - SP', postal_code: '01310-100', country: 'BR', phone: '+55 11 98123-4567', currency: 'BRL', amount: '2380.60', notes: 'Cliente desde 2019 🎉' },
  { name: 'Kwame Mensah', word: 'mensah', address: 'House No. 7, Oxford Street, Osu', city: 'Accra', postal_code: 'GA-019-2245', country: 'GH', phone: '+233 30 277 4019', currency: 'GHS', amount: '5400.00', notes: null },
  { name: "Ana Lucía O'Neill", word: "o'neill", address: 'Av. Providencia 1208, depto. 54', city: 'Santiago', postal_code: '7500000', country: 'CL', phone: '+56 2 2345 6789', currency: 'CLP', amount: '650000', notes: '👩🏽‍💻 Works from home' },
]

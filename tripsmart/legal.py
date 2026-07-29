"""Legal pages (Terms of Use + Privacy Policy) served by the backend.

The Zalo Mini App console requires public URLs for both when submitting for
review. Kept as simple self-contained HTML so there is nothing extra to host:
    https://zah-40.123c.vn/terms
    https://zah-40.123c.vn/privacy
"""

from __future__ import annotations

_STYLE = """
<style>
  body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
         max-width: 720px; margin: 0 auto; padding: 24px 20px 60px;
         color: #16202b; line-height: 1.65; }
  h1 { font-size: 26px; margin: 8px 0 4px; }
  h2 { font-size: 18px; margin: 26px 0 8px; }
  .meta { color: #5a6b7b; font-size: 13.5px; margin-bottom: 18px; }
  li { margin: 6px 0; }
  a { color: #1e7a82; }
  .note { background: #eef5f5; border: 1px solid #dcebeb; border-radius: 10px;
          padding: 12px 14px; font-size: 14.5px; }
</style>
"""

TERMS_HTML = f"""<!doctype html><html lang="vi"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Điều khoản sử dụng — Odysseus</title>{_STYLE}</head><body>
<h1>Điều khoản sử dụng</h1>
<div class="meta">Odysseus (Zalo TripSmart) — Zalo Mini App · Hiệu lực từ 30/07/2026</div>

<p class="note">Odysseus là <b>trợ lý du lịch dùng trí tuệ nhân tạo (AI)</b> chạy trong
Zalo Mini App. Bằng việc sử dụng ứng dụng, bạn đồng ý với các điều khoản dưới đây.</p>

<h2>1. Dịch vụ cung cấp</h2>
<p>Odysseus hỗ trợ người dùng lên kế hoạch du lịch qua hội thoại: gợi ý điểm đến,
tra cứu và so sánh giá vé máy bay, khách sạn từ các nguồn dữ liệu bên thứ ba
(Google Flights, Google Hotels, Google Maps), tham khảo quy định visa/nhập cảnh,
và dựng lịch trình theo ngày trên bản đồ.</p>

<h2>2. Tính chất thông tin — quan trọng</h2>
<ul>
  <li><b>Thông tin chỉ mang tính tham khảo.</b> Giá vé, giá phòng thay đổi liên tục
      theo thời gian thực và có thể khác với giá cuối cùng tại nơi bán.</li>
  <li>Nội dung do AI tạo ra có thể chưa đầy đủ hoặc chưa chính xác. Bạn nên
      <b>tự kiểm chứng</b> trước khi ra quyết định chi tiêu.</li>
  <li>Quy định <b>visa/nhập cảnh</b> có thể thay đổi — luôn xác minh với nguồn
      chính thức (đại sứ quán, cơ quan xuất nhập cảnh, hãng bay) trước chuyến đi.</li>
</ul>

<h2>3. Đặt chỗ và thanh toán</h2>
<p>Odysseus <b>không phải là đại lý du lịch</b> và <b>không xử lý thanh toán</b>.
Tính năng "Đặt ngay" chuyển hướng bạn tới trang của đối tác cung cấp dịch vụ;
giao dịch (nếu có) diễn ra và chịu sự điều chỉnh bởi điều khoản của đối tác đó.
Ứng dụng không thu thập, không lưu trữ thông tin thẻ hay tài khoản ngân hàng.</p>

<h2>4. Dữ liệu của bạn</h2>
<p>Ứng dụng chỉ lưu sở thích du lịch bạn tự khai (thành phố xuất phát, khẩu vị,
mức ngân sách…) và lịch sử hội thoại trong thời gian ngắn để giữ mạch trò chuyện.
Chúng tôi không yêu cầu và không lưu số hộ chiếu, ngày sinh đầy đủ, số điện thoại
hay thông tin thanh toán. Chi tiết tại <a href="/privacy">Chính sách bảo mật</a>.
Bạn có thể yêu cầu xoá dữ liệu bất kỳ lúc nào bằng cách nhắn "xoá thông tin của tôi"
trong ứng dụng.</p>

<h2>5. Sử dụng hợp lệ</h2>
<ul>
  <li>Không sử dụng ứng dụng cho mục đích trái pháp luật, spam, phá hoại,
      dò quét hệ thống hoặc trục lợi tự động.</li>
  <li>Hệ thống áp dụng giới hạn tần suất sử dụng để bảo đảm chất lượng dịch vụ
      cho mọi người dùng.</li>
  <li>Chúng tôi có thể tạm ngưng phục vụ các tài khoản lạm dụng.</li>
</ul>

<h2>6. Giới hạn trách nhiệm</h2>
<p>Dịch vụ được cung cấp "nguyên trạng" (as-is). Trong phạm vi pháp luật cho phép,
chúng tôi không chịu trách nhiệm cho thiệt hại phát sinh từ việc sử dụng thông tin
tham khảo trong ứng dụng, gián đoạn dịch vụ, hoặc sai lệch dữ liệu từ nguồn bên
thứ ba.</p>

<h2>7. Sở hữu trí tuệ</h2>
<p>Tên, logo Odysseus và mã nguồn ứng dụng thuộc về nhóm phát triển. Dữ liệu bản
đồ © OpenStreetMap contributors; dữ liệu giá thuộc các nguồn tương ứng.</p>

<h2>8. Thay đổi điều khoản</h2>
<p>Điều khoản có thể được cập nhật; phiên bản mới nhất luôn được đăng tại trang này
với ngày hiệu lực tương ứng. Tiếp tục sử dụng ứng dụng nghĩa là bạn đồng ý với
phiên bản hiện hành.</p>

<h2>9. Liên hệ</h2>
<p>Mọi câu hỏi về điều khoản: liên hệ nhóm phát triển Odysseus qua Official Account
của ứng dụng trên Zalo.</p>
</body></html>"""

PRIVACY_HTML = f"""<!doctype html><html lang="vi"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chính sách bảo mật — Odysseus</title>{_STYLE}</head><body>
<h1>Chính sách bảo mật</h1>
<div class="meta">Odysseus (Zalo TripSmart) — Zalo Mini App · Hiệu lực từ 30/07/2026</div>

<p class="note">Nguyên tắc của Odysseus: <b>thu thập ít nhất có thể</b> — chỉ những gì
cần để trợ lý du lịch hoạt động, và không bao giờ là dữ liệu nhạy cảm.</p>

<h2>1. Dữ liệu chúng tôi lưu</h2>
<ul>
  <li><b>Sở thích du lịch tự khai</b> (nếu bạn chia sẻ): thành phố xuất phát, mức
      ngân sách, khẩu vị ăn uống, sở thích chuyến bay/khách sạn, thông tin đi cùng
      trẻ nhỏ ở dạng khoảng tuổi. Lưu dưới định danh Zalo Mini App của bạn.</li>
  <li><b>Lịch sử hội thoại gần nhất</b>: giữ tối đa 48 giờ để duy trì mạch trò
      chuyện, sau đó tự xoá.</li>
  <li><b>Dữ liệu tổng hợp ẩn danh</b>: tên điểm đến được tìm kiếm (không gắn với
      người tìm) để gợi ý xu hướng cho cộng đồng.</li>
</ul>

<h2>2. Dữ liệu chúng tôi KHÔNG thu thập</h2>
<p>Số hộ chiếu/CCCD, ngày sinh đầy đủ, số điện thoại, địa chỉ nhà, thông tin thẻ
hoặc tài khoản ngân hàng. Hệ thống có bộ lọc tự động <b>từ chối lưu</b> các giá trị
trông giống dữ liệu cá nhân nhạy cảm, kể cả khi bạn vô tình cung cấp.</p>

<h2>3. Dữ liệu được dùng như thế nào</h2>
<ul>
  <li>Cá nhân hoá gợi ý du lịch cho chính bạn (ví dụ nhớ bạn xuất phát từ TP.HCM).</li>
  <li>Nội dung hội thoại được gửi tới nhà cung cấp mô hình AI (Anthropic Claude)
      để tạo câu trả lời; truy vấn giá được gửi tới nguồn dữ liệu (SerpApi/Google)
      ở dạng <b>không kèm danh tính</b>.</li>
  <li>Không bán, không chia sẻ dữ liệu cá nhân cho bên thứ ba vì mục đích quảng cáo.</li>
</ul>

<h2>4. Quyền của bạn</h2>
<ul>
  <li><b>Xoá toàn bộ</b> sở thích đã lưu bất cứ lúc nào: nhắn "hãy quên thông tin
      của tôi" trong ứng dụng — hệ thống xoá ngay và xác nhận lại với bạn.</li>
  <li>Sửa một sở thích: chỉ cần nói lại điều mới ("mình chuyển ra Hà Nội rồi").</li>
</ul>

<h2>5. Lưu trữ & bảo mật</h2>
<p>Dữ liệu lưu trên máy chủ đặt tại Việt Nam, truy cập qua HTTPS. Khoá API và dữ
liệu vận hành được tách khỏi mã nguồn công khai.</p>

<h2>6. Thay đổi chính sách</h2>
<p>Phiên bản mới nhất luôn đăng tại trang này kèm ngày hiệu lực.</p>

<h2>7. Liên hệ</h2>
<p>Câu hỏi về dữ liệu cá nhân: liên hệ nhóm phát triển Odysseus qua Official
Account của ứng dụng trên Zalo.</p>
</body></html>"""

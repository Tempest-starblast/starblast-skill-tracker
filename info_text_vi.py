# -*- coding: utf-8 -*-
"""Trang Thông tin bằng tiếng Việt. Bản gốc là info_text_en.py."""

TITLE = "Thông tin"
SUB = "Trang này hoạt động thế nào, nói ngắn gọn."
FOOT = 'Có thắc mắc? Hỏi [[CONTACT]] trên Discord.'

CARDS = [
 ("Đây là gì",
  '<p class="lead">Bảng xếp hạng kỹ năng cho chế độ đồng đội của Starblast. Chơi trận đồng'
  ' đội, thắng, và điểm của bạn tăng lên. Không phải cài gì, không phải đăng ký gì'
  ' &mdash; bạn có tên trên bảng ngay khi thắng một trận mà chúng tôi đang theo dõi.</p>'),

 ("Bắt đầu thế nào",
  '<ol>'
  '<li>Mở thẻ <a href="/play">Chơi</a> và chọn một trận được đánh dấu là đang theo dõi.</li>'
  '<li>Bấm <b>Chơi</b>. Tên của bạn được sao chép, sẵn sàng dán vào Starblast.</li>'
  '<li>Chơi trận đó. Khi trận kết thúc, kết quả hiện ở đây trong vòng một phút.</li>'
  '</ol>'
  '<p>Chỉ cần vậy thôi. Đăng nhập là tuỳ bạn, và chỉ cần cho những phần thêm ở dưới.</p>'),

 ("Trận nào được tính",
  '<p>Chúng tôi chỉ theo dõi được vài trận cùng lúc, nên không phải trận nào cũng tính.'
  ' Một trận có thể được theo dõi khi đã <b>20 phút</b>, cho tới khi được 90 phút, và cần'
  ' ít nhất bốn người chơi.</p>'
  '<p>Thẻ <a href="/play">Chơi</a> cho biết chính xác những phòng nào đang được theo dõi'
  ' ngay lúc này. Nếu một trận không có trong danh sách đó thì không ghi nhận gì cả'
  ' &mdash; và cũng không có chuyện đến muộn.</p>'),

 ("Điểm của bạn",
  '<p>Ai cũng bắt đầu ở <b>[[ELO]]</b>. Một trận làm bạn thay đổi nhiều nhất <b>[[K]]</b>'
  ' điểm.</p>'
  '<p>Thay đổi bao nhiêu là tuỳ bạn thắng ai. Thắng đội mạnh hơn thì gần như được trọn'
  ' vẹn; thắng đội yếu hơn nhiều thì gần như không được gì. Thua cũng vậy nhưng ngược lại.'
  ' Hai đội ngang nhau thì thay đổi đúng một điểm.</p>'
  '<p>Sức mạnh của một đội là trung bình của hai người giỏi nhất, nên cày đội yếu sẽ không'
  ' kéo bạn lên &mdash; muốn lên thì phải thắng những người có điểm cao.</p>'),

 ("Trọn vẹn và một nửa",
  '<p>Nếu bạn đã ở trong trận từ trước khi chúng tôi bắt đầu theo dõi, trận đó tính trọn'
  ' vẹn. Vào một trận đang được theo dõi thì vẫn tính, nhưng <b>một nửa</b> &mdash; cho cả'
  ' bên thắng lẫn bên thua. Thẻ Chơi nói rõ trận nào là trận nào trước khi bạn vào.</p>'),

 ("Hai điều nên biết",
  '<p><b>Thoát sớm không tránh được trận thua.</b> Đội thua bị tính theo đội hình đông'
  ' nhất của mình, chứ không phải theo ai còn trụ lại đến cuối.</p>'
  '<p><b>Điểm dưới [[MINSCORE]] thì không được tính</b>, dù thắng hay thua. Ngồi trong phòng'
  ' không phải là chơi.</p>'),

 ("Hai cái tên",
  '<p><b>Tên tài khoản</b> là dòng trên bảng xếp hạng thuộc về bạn. Điểm của bạn nằm ở đó,'
  ' và nó không đổi khi bạn đổi tên trong game. Đặt ở'
  ' <a href="/settings">Cài đặt</a>.</p>'
  '<p><b>Tên khi chơi</b> là tên bạn đang dùng trong Starblast lúc này. Đặt ở trang'
  ' <a href="/play">Chơi</a>, và đổi bao nhiêu lần cũng được &mdash; nó chỉ để nhận ra tàu'
  ' của bạn trong phòng, vậy thôi.</p>'
  '<p>Ban đầu hai tên giống nhau, và với hầu hết mọi người thì vẫn vậy. Chúng chỉ khác nhau'
  ' nếu bạn chơi dưới một cái tên khác một thời gian.</p>'),

 ("Báo danh trước trận, và dấu tích xanh",
  '<p>Bấm <b>Chơi</b> trước một trận chính là thứ nối hai cái tên lại. Trang web tìm trong'
  ' phòng đó một con tàu mang <b>tên khi chơi</b> của bạn, xác định con tàu đó là bạn, rồi'
  ' ghi kết quả vào <b>tên tài khoản</b> của bạn &mdash; nhờ vậy điểm của bạn dồn về một'
  ' chỗ, dù trong game bạn tên là gì.</p>'
  '<p>Vậy nên hãy để tên khi chơi ở trang Chơi giống hệt tên trên tàu của bạn. Chính nó mới'
  ' phải khớp; tên tài khoản thì không cần.</p>'
  '<p><b>Nếu bạn không báo danh</b>, kết quả sẽ rơi vào đúng cái tên mà game báo về. Nó chỉ'
  ' tính cho bạn nếu cái tên đó là của bạn.</p>'
  '<p>Dấu <b>&#10003;</b> cạnh một cái tên nghĩa là người đó đã bật Bảo vệ: chỉ những trận'
  ' họ có báo danh mới được tính. Đó là cách tính chặt hơn và chậm hơn, và không bắt buộc'
  ' &mdash; xem trong <a href="/settings">Cài đặt</a>.</p>'),

 ("Bang hội",
  '<p>Bang hội là một nhóm người chơi dùng chung một thẻ tên. Trang của bang cho thấy danh'
  ' sách thành viên xếp theo kỹ năng, thành tích chung và nơi bang thường chơi.</p>'
  '<p><b>Cách vào bang.</b> Mở trang của bang và bấm <b>Xin gia nhập</b>, hoặc dùng liên'
  ' kết mời do bang chủ đưa. Dù cách nào thì bang chủ vẫn là người quyết định. Nếu tên'
  ' trong game của bạn đã mang thẻ của bang vào lúc bang được lập, bạn được thêm vào tự'
  ' động.</p>'
  '<p><b>Thẻ của bạn hiện đúng như cách nó được viết</b> &mdash; kể cả chữ hoa mỹ. Bản chữ'
  ' thường chỉ dùng ở phía sau, để mọi cách viết của một thẻ đều tính là một bang và tìm'
  ' kiếm kiểu nào cũng ra.</p>'
  '<p><b>Cấp bậc.</b> Bang chủ có thể phong phó bang và điều hành. Điều hành xoá được thành'
  ' viên thường; phó bang làm được mọi thứ bang chủ làm, trừ xoá bang và động đến một phó'
  ' bang khác. Không ai xoá được người cùng cấp hoặc cao hơn mình.</p>'),

 ("Một cái tên đã có trên bảng",
  '<p>Gõ tên đó ở <a href="/settings">Cài đặt</a>: nếu chưa ai sở hữu, nó là của bạn ngay.'
  ' Nếu nó đã có thành tích, trang sẽ mời bạn <b>nhận</b> tên đó: nó thành của bạn vào lần'
  ' tới cái tên ấy thắng một trận được theo dõi &mdash; đó là cách chúng tôi biết đúng là'
  ' bạn, chứ không phải ai đó lấy điểm của người khác.</p>'
  '<p>Cũng vậy nếu một cái tên đã có trên bảng <b>đọc lên</b> giống hệt cái bạn vừa gõ'
  ' &mdash; một tên chữ thường so với bản viết bằng chữ hoa mỹ. Các trận của bạn đang rơi'
  ' vào dòng đó, nên trang sẽ mời bạn nhận dòng đó. Nếu đúng là người khác thật, cứ lưu tên'
  ' của bạn như thường.</p>'),

 ("Làm bang chủ",
  '<p>Bang hội được cấp bằng tay. Hãy xin ở trang <a href="/clans">Bang hội</a>, rồi'
  ' [[CONTACT]] duyệt hoặc từ chối trên Discord. Nếu bị từ chối, bạn vẫn có thể xin'
  ' lại.</p>'
  '<p>Được duyệt rồi thì bạn nhận thẻ của mình, và thẻ <b>Bang của bạn</b> xuất hiện với'
  ' mọi thứ ở một chỗ: liên kết mời, ai đang chờ vào, danh sách thành viên, cấp bậc, khu'
  ' vực và xoá bang.</p>'),

 ("Ngôn ngữ",
  '<p>Chọn ngôn ngữ ở đầu trang, trên bất kỳ trang nào &mdash; English, Español, Français,'
  ' Deutsch, Italiano, Русский, Tiếng Việt hoặc 中文. Toàn bộ trang web đã được dịch, kể cả'
  ' trang này. Bản tiếng Anh là bản gốc, nên nếu chỗ nào dịch nghe lạ thì nghĩa gốc nằm ở'
  ' đó.</p>'),

 ("Discord",
  '<p>Bot làm được gần như mọi thứ trang web làm &mdash; bảng xếp hạng, hồ sơ của bạn, bang'
  ' hội, xin gia nhập và đặt cấp bậc. Xin [[CONTACT]] một lời mời, rồi dùng <b>/help</b> để'
  ' xem các lệnh.</p>'),

 ("Chúng tôi biết gì về bạn",
  '<p><b>Không lưu địa chỉ IP nào cả.</b> Không lưu khi bạn vào trang, không lưu khi bạn'
  ' bấm Chơi, không lưu khi bạn đăng nhập.</p>'
  '<p>Đăng nhập bằng Discord cho chúng tôi biết id tài khoản và tên người dùng của bạn.'
  ' Google cho một id tài khoản. Chỉ vậy thôi &mdash; không có email, và không có gì để'
  ' liên lạc với bạn.</p>'
  '<p>Mã nguồn của trang là công khai, nên tất cả những điều này có thể kiểm chứng chứ'
  ' không phải tin suông.</p>'),

 ("Câu hỏi thường gặp",
  '<div class="qa">'
  '<b>Tôi thắng rồi mà không thấy gì cả.</b>'
  ' Nhiều khả năng trận đó không nằm trong số được theo dõi. Thẻ Chơi liệt kê chúng trước'
  ' khi bạn vào.'
  '<b>Tên tôi xuất hiện hai lần trên bảng.</b>'
  ' Viết khác đi thì tính là người chơi khác, vì game chỉ báo về có vậy. Hãy nhận cái tên'
  ' bạn thật sự dùng.'
  '<b>Bảng xếp hạng bị đặt lại.</b>'
  ' Điểm số vẫn đang trong giai đoạn thử và có thể bị xoá lần nữa. Không có gì bạn làm là'
  ' uổng phí; bảng chỉ bắt đầu lại thôi.'
  '<b>Có gì đó không đúng.</b>'
  ' Hãy nói ở trang <a href="/reports">Báo cáo</a> hoặc nhắn [[CONTACT]] trên Discord. Sẽ'
  ' có người đọc.'
  '</div>'),
]

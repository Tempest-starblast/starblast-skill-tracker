# -*- coding: utf-8 -*-
"""Trang Thông tin bằng tiếng Việt. Bản gốc là info_text_en.py."""

TITLE = "Thông tin"
SUB = "Trang này hoạt động thế nào, nói ngắn gọn."
SEARCH = "Tìm trong trang này…"
NOMATCH = "Không có gì trên trang này khớp với đó."
STALE = ()
FOOT = 'Có thắc mắc? Hỏi [[CONTACT]] trên Discord.'

CARDS = [
 ('Đây là gì',
  '<p class="lead">Bảng xếp hạng kỹ năng cho chế độ đồng đội của Starblast. Chơi các trận đồng đội, thắng, và điểm của bạn tăng. Không cần cài đặt, không cần đăng ký &mdash; bạn có mặt trên bảng ngay khi chơi một trận mà chúng tôi tính điểm.</p>'),

 ('Bắt đầu thế nào',
  '<ol><li>Mở thẻ <a href="/play">Chơi</a> và chọn một trận.</li>'
  '<li>Nhấn <b>Chơi</b>. Tên của bạn được sao chép, sẵn sàng dán vào Starblast.</li>'
  '<li>Chơi. Khi trận kết thúc, kết quả xuất hiện ở đây trong khoảng mười phút.</li>'
  '</ol>'
  '<p>Chỉ cần vậy thôi. Đăng nhập là tuỳ bạn, và chỉ cần cho những phần thêm ở dưới.</p>'),

 ('Trận nào được tính',
  '<p>Mọi trận đồng đội đang diễn ra đều được theo dõi, ngay từ lúc phòng xuất hiện. Không giới hạn số trận cùng lúc và không cần số người chơi tối thiểu để phòng được theo dõi.</p>'
  '<p>Để được <b>tính điểm</b>, trận phải kéo dài <b>ít nhất mười phút</b>. Các trận ngắn hơn vẫn được ghi lại và có thể xem lại, nhưng không làm thay đổi điểm của ai.</p>'
  '<p>Trong một trận được tính điểm, <b>tất cả</b> những ai có mặt <b>mười phút</b> và đạt điểm tối thiểu đều được tính, dù thắng hay thua. Chỉ thời gian mà hệ thống theo dõi thấy mới được tính.</p>'
  '<p>Thẻ <a href="/play">Chơi</a> liệt kê mọi trận đang diễn ra và cho biết hệ thống đã theo dõi chưa; một phòng mới được theo dõi chỉ sau vài giây. Nếu trận đang diễn ra, nó được tính.</p>'
  '<p>Thời gian bạn chơi trong các trận được tính điểm được cộng dồn trên hồ sơ của bạn &mdash; tổng cộng, và hai tuần gần nhất bên cạnh. Hệ thống theo dõi đo nó, nên nó theo cùng các quy tắc ở trên: một trận không tính điểm, hoặc một phòng không ai theo dõi, không được tính. Việc đếm bắt đầu từ ngày 21 tháng 9 năm 2026.</p>'),

 ('Điểm của bạn',
  '<p>Ai cũng bắt đầu từ <b>[[ELO]]</b>. Trong <b>[[NEWGAMES]]</b> trận đầu tiên, một trận có thể làm bạn thay đổi tới <b>[[KNEW]]</b> điểm, để bạn nhanh chóng tìm được trình độ của mình; sau đó, tới <b>[[KEST]]</b>.</p>'
  '<p>Bạn thay đổi bao nhiêu phụ thuộc vào việc bạn thắng ai. Thắng một bên mạnh hơn được gần như tối đa; thắng một bên yếu hơn nhiều gần như không được gì. Thua cũng vậy, theo chiều ngược lại.</p>'
  '<p>Sức mạnh của một đội là trung bình của mọi người trong đội, nên đánh các đội yếu sẽ không đưa bạn lên &mdash; leo hạng nghĩa là thắng những người có điểm cao. Người đứng cạnh bạn cũng quan trọng: mức thay đổi của bạn trộn điểm của chính bạn với trung bình đội, nên gánh đồng đội yếu tới chiến thắng được nhiều hơn cùng chiến thắng đó trong một đội toàn người mạnh &mdash; và thua cạnh đồng đội yếu mất ít hơn.</p>'),

 ('Trọn vẹn và một nửa',
  '<p>Vì hệ thống theo dõi mỗi trận từ đầu, nó biết chính xác khi nào tàu của bạn gia nhập bên cuối cùng giành chiến thắng. Gia nhập trong nửa đầu trận, chiến thắng được tính <b>trọn vẹn</b>. Gia nhập trong nửa sau, nó được tính <b>nhiều nhất là một nửa</b> &mdash; và càng ít nếu bạn có mặt càng ít.</p>'
  '<p>Trận thua luôn được tính trọn vẹn: đến muộn không phải là cách để thua ít hơn. Việc tính dựa trên thời điểm bạn thật sự vào trận, không phải lúc bạn nhấn Chơi.</p>'),

 ('Những quy tắc nên biết',
  '<p><b>Cần có điểm, không chỉ có mặt.</b> Để được tính điểm, bạn phải đạt <b>[[MINPEAK]]</b> vào một lúc nào đó trong trận nếu bên bạn thắng, hoặc <b>[[MINLOSE]]</b> nếu bên bạn thua. Ngồi trong phòng không phải là chơi.</p>'
  '<p><b>Rời đi sớm không tránh được trận thua.</b> Tất cả những ai đã chơi cho bên thua đều bị tính thua, dù họ còn ở đó lúc kết thúc hay không.</p>'
  '<p><b>Bỏ một bên trông như đã thua sẽ không cho bạn màn lội ngược dòng của họ.</b> Nếu bên bạn có dưới 25% cơ hội thắng khi bạn rời đi, và bạn vẫn vắng mặt khi họ thắng, hơn mười phút sau, thì chiến thắng không phải của bạn. Trang tài khoản của bạn sẽ ghi rõ.</p>'),

 ("Hai cái tên",
  '<p><b>Tên tài khoản</b> là dòng trên bảng xếp hạng thuộc về bạn. Điểm của bạn nằm ở đó,'
  ' và nó không đổi khi bạn đổi tên trong game. Đặt ở <a href="/settings">Cài'
  ' đặt</a>.</p><p><b>Tên khi chơi</b> là tên bạn đang dùng trong Starblast lúc này. Đặt ở'
  ' trang <a href="/play">Chơi</a>, và đổi bao nhiêu lần cũng được &mdash; nhờ nó chúng tôi'
  ' nhận ra tàu của bạn trong phòng, và một trận chơi dưới tên đó được tính cho tài khoản'
  ' của bạn.</p><p>Ban đầu hai tên giống nhau, và với hầu hết mọi người thì vẫn vậy. Chúng'
  ' chỉ khác nhau nếu bạn chơi dưới một cái tên khác một thời gian.</p>'),

 ("Báo danh trước trận, và dấu tích xanh",
  '<p>Bấm <b>Chơi</b> trước một trận chính là thứ nối hai cái tên lại. Trang web tìm trong'
  ' phòng đó một con tàu mang <b>tên khi chơi</b> của bạn, xác định con tàu đó là bạn, rồi'
  ' ghi kết quả vào <b>tên tài khoản</b> của bạn &mdash; nhờ vậy điểm của bạn dồn về một'
  ' chỗ, dù trong game bạn tên là gì.</p><p>Vậy nên hãy để tên khi chơi ở trang Chơi giống'
  ' hệt tên trên tàu của bạn. Chính nó mới phải khớp; tên tài khoản thì không'
  ' cần.</p><p><b>Nếu bạn không báo danh</b>, một trận dưới tên khi chơi của bạn vẫn được'
  ' tính cho bạn. Báo danh chỉ thêm bằng chứng con tàu nào là của bạn: nếu ai đó bay dưới'
  ' tên bạn trong cùng phòng, trận sẽ bị giữ lại trừ khi bạn đã báo danh, và <b>Bảo vệ</b>'
  ' chỉ tính những trận bạn có báo danh. Một tên khi chơi mà hai tài khoản cùng nhận thì'
  ' không tính cho bên nào.</p><p>Dấu <b>&#10003;</b> cạnh một cái tên nghĩa là người đó đã'
  ' bật Bảo vệ: chỉ những trận họ có báo danh mới được tính. Đó là cách tính chặt hơn và'
  ' chậm hơn, và không bắt buộc &mdash; xem trong <a href="/settings">Cài đặt</a>.</p>'),

 ("Bang hội",
  '<p>Bang hội là một nhóm người chơi dùng chung một thẻ tên. Trang của bang cho thấy danh'
  ' sách thành viên xếp theo kỹ năng, thành tích chung, số trận sinh tồn bang đã thắng, và'
  ' nơi bang thường chơi.</p><p><b>Cách vào bang.</b> <a href="/social">Social</a> gợi ý'
  ' những bang có thành viên chơi ở tầm của bạn, và cho bạn xem mọi bang đang nhận đơn xin'
  ' gia nhập. Bạn cũng có thể mở trang của bang và bấm <b>Xin gia nhập</b>, hoặc dùng liên'
  ' kết mời do bang chủ đưa. Dù cách nào thì bang chủ vẫn là người quyết định. Nếu tên trong'
  ' game của bạn đã mang thẻ của bang vào lúc bang được lập, bạn được thêm vào tự'
  ' động.</p><p><b>Thẻ của bạn hiện đúng như cách nó được viết</b> &mdash; kể cả chữ hoa mỹ.'
  ' Bản chữ thường chỉ dùng ở phía sau, để mọi cách viết của một thẻ đều tính là một bang và'
  ' tìm kiếm kiểu nào cũng ra. Bang chủ có thể thêm các cách viết khác của thẻ ở <a'
  ' href="/myclan">Bang của bạn</a>, và mỗi thành viên chọn cách viết mình đeo ở <a'
  ' href="/account">Tài khoản của bạn</a>.</p><p><b>Một trận dưới thẻ của bang bạn được tính'
  ' cho bạn</b>, dù thẻ được gõ theo cách viết nào. Chỉ thành viên của bang đó mới được khớp'
  ' theo cách này, và phần sau thẻ phải là tên của bạn.</p><p><b>Tên tài khoản chỉ là chính'
  ' bạn.</b> Khi bạn vào một bang, thẻ được gỡ khỏi tên tài khoản và hiện bên cạnh như một'
  ' huy hiệu, nên thẻ có thể đổi, bang của bạn cũng có thể đổi, mà thành tích của bạn không'
  ' phải dời đi đâu. Trang tài khoản sẽ hỏi trước khi lưu một cái tên có mang'
  ' thẻ.</p><p><b>Cấp bậc.</b> Bang chủ có thể phong phó bang và điều hành. Điều hành xoá'
  ' được thành viên thường; phó bang làm được mọi thứ bang chủ làm, trừ xoá bang và động đến'
  ' một phó bang khác. Không ai xoá được người cùng cấp hoặc cao hơn mình.</p>'),

 ('Một cái tên đã có trên bảng',
  '<p>Nhập nó trong <a href="/settings">Cài đặt</a> và, nếu chưa ai sở hữu, nó là của bạn ngay. Nếu nó đã có lịch sử, trang sẽ đề nghị bạn <b>xác nhận quyền sở hữu</b> thay vào đó. Hãy chứng minh nó là của bạn bằng cách chơi một trận Deathmatch xếp hạng &mdash; lệnh <b>/proveclaim</b> của bot Discord sẽ hướng dẫn bạn &mdash; hoặc chờ [[CONTACT]] xem xét. Khi yêu cầu còn mở, nó hiện trên trang của người chơi đó, để chủ thật có thể báo cáo.</p>'
  '<p>Điều tương tự xảy ra nếu một tên đã có trên bảng <b>đọc</b> giống tên bạn nhập &mdash; một tên thường so với phiên bản dùng chữ trang trí. Các trận của bạn đang được ghi vào dòng đó, nên bạn được đề nghị dòng đó. Nếu đó thật sự là người khác, cứ lưu tên của bạn.</p>'),

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

 ('Câu hỏi thường gặp',
  '<div class="qa"><b>Tôi thắng nhưng không có gì xảy ra.</b> Kết quả đến khoảng mười phút sau khi trận kết thúc. Nếu lâu hơn, thường là do một trong những điều sau: trận kéo dài dưới mười phút, bạn không có mặt đủ mười phút cần thiết, điểm của bạn chưa đạt mức tối thiểu, hoặc bạn đã rời bên mình khi họ đang thua và vẫn vắng mặt khi họ thắng.<b>Tên tôi xuất hiện hai lần.</b> Cách viết khác được tính là người chơi khác, vì trò chơi chỉ báo có vậy. Hãy xác nhận tên bạn thật sự dùng để chơi.<b>Bảng đã bị đặt lại.</b> Điểm vẫn đang được thử nghiệm và có thể bị xoá lại. Không có gì bạn làm là uổng phí; bảng chỉ bắt đầu lại.<b>Có gì đó không đúng.</b> Hãy báo ở <a href="/reports">Báo cáo</a> hoặc nói với [[CONTACT]] trên Discord. Một người thật sẽ đọc.</div>'),
 ("Hạng",
  '<p>Hạng của bạn là vị trí của bạn trong số tất cả người chơi đã được xếp hạng trên bảng tổng, không phải một số điểm — nên nó thay đổi khi những người quanh bạn thay đổi. Người chơi còn trong vài trận đầu tiên không được tính.</p>'
  '[[RANKS]]'),
]

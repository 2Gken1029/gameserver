DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `select_difficulty` int DEFAULT NULL,
  `joined_user_count` int DEFAULT NULL,
  `room_status` int DEFAULT 1,
  PRIMARY KEY (`room_id`)
);
DROP TABLE IF EXISTS `room_members`;
CREATE TABLE `room_members` (
  `room_id` bigint NOT NULL,
  `select_difficulty` int DEFAULT NULL,
  `user_id` bigint NOT NULL,
  `token` varchar(255) DEFAULT NULL,
  `is_host` BOOLEAN NOT NULL,
  `score` int DEFAULT NULL,
  `perfect` int DEFAULT NULL,
  `great` int DEFAULT NULL,
  `good` int DEFAULT NULL,
  `bad` int DEFAULT NULL,
  `miss` int DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);
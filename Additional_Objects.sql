-- Additional Objects
--  These objects weren't created in the backup in order to save space
--  But feel free to create them by running these scripts if you like


-- primary key for tickets
ALTER TABLE [dbo].[Ticket] 
ADD CONSTRAINT [PK_Ticket] PRIMARY KEY NONCLUSTERED ([ticket_number], [violation_code])
ON [Data_FG];


-- view to join all tables together
CREATE VIEW [dbo].[vw_ParkingTickets]
AS
SELECT
	t.ticket_number,
	t.plate_number,
	t.license_state,
	t.license_type,
	t.car_make,
	t.issue_date,
	t.violation_location,
	t.violation_code,
	v.[Description] AS violation_description,
	v.Cost AS violation_cost,
	t.badge,
	t.unit,
	q.[Description] AS ticket_queue,
	d.[Description] AS hearing_disposition
FROM [dbo].[Ticket] t
LEFT JOIN [dbo].[Violation] v ON t.violation_code = v.Code
LEFT JOIN [dbo].[TicketQueue] q ON t.ticket_queue_id = q.ID
LEFT JOIN [dbo].[HearingDisposition] d ON t.hearing_dispo_id = d.ID;

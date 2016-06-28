from acis_thermal_check import dea_check

class DEATestOpts(object):
    def __init__(self, run_start, days, ccd_count, fep_count, vid_board,
                 clocking, simpos, pitch):
        self.run_start = run_start
        self.days = days
        self.ccd_count = ccd_count
        self.fep_count = fep_count
        self.vid_board = vid_board
        self.clocking = clocking
        self.simpos = simpos
        self.pitch = pitch

def test_dea_model():
    opt = DEATestOpts()
    results = dea_check.driver(opt)
